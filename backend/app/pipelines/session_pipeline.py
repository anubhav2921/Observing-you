"""
backend/app/pipelines/session_pipeline.py — Isolated session monitor pipeline.
Performs frame validation, flow control, perception arbitration, and rationale generation.
"""

from __future__ import annotations

import base64
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

import backend.app.core.config as config
from backend.app.schemas.events import (
    AlertData,
    DecisionRationale,
    ObservationData,
    RecommendationData,
    StateUpdateEvent,
)
from backend.app.services.behavior.behavior_types import (
    BehaviorLabel,
    UpperBodyDecision,
    UpperBodyFeatures,
)
from backend.app.services.decision.state_machine import (
    ALERT_STATES,
    STATE_DISPLAY,
    StudyState,
)
from backend.app.services.detection.focus_monitor import FocusMonitor
from backend.app.services.detection.yolo_service import YOLOService
from backend.app.services.recommendation.recommendation_engine import RecommendationEngine

WEB_ALERT_CONFIG: Dict[StudyState, Tuple[str, int]] = {
    StudyState.CAMERA_ERROR:        ("/assets/audio/distraction_alert.mp3", 1),
    StudyState.STUDENT_ABSENT:      ("/assets/audio/distraction_alert.mp3", 2),
    StudyState.FACE_OCCLUDED:       ("/assets/audio/occlusion_alert.mp3", 3),
    StudyState.POSSIBLE_DROWSINESS: ("/assets/audio/drowsiness_alert.mp3", 4),
    StudyState.DISTRACTED:          ("/assets/audio/distraction_alert.mp3", 5),
    StudyState.LOOKING_AWAY:        ("/assets/audio/distraction_alert.mp3", 5),
    StudyState.INACTIVITY_WARNING:  ("/assets/audio/distraction_alert.mp3", 5),
}

MAX_FRAME_BYTES = 2_500_000  # 2.5 MB maximum frame payload limit


class SessionPipeline:
    """
    Manages an isolated monitoring session for a connected Web client.
    Thread-safe and completely independent from other sessions.
    """

    def __init__(self, session_id: Optional[str] = None) -> None:
        self.session_id = session_id or uuid.uuid4().hex
        self.focus_monitor = FocusMonitor(logger=None)
        self.yolo_service = YOLOService.get_instance()

        self.start_time = time.monotonic()
        self.frame_count = 0
        self.active = True

        # YOLO stride caching to avoid timer resets on skipped frames
        self.cached_yolo_info = {
            "person_detected": False,
            "person_conf": 0.0,
            "person_box": None,
            "phone_detected": False,
            "book_detected": False,
            "laptop_detected": False,
        }

        # Alert tracking
        self.active_alert_name: Optional[str] = None
        self.active_alert_priority: int = 99
        self.last_alert_time: float = 0.0
        self.last_alert_state: Optional[StudyState] = None

        # FPS Tracking
        self.last_frame_time = time.monotonic()
        self.fps = 0.0
        self.calibration_data: Optional[Dict[str, Any]] = None

    def process_frame_bytes(self, raw_bytes: bytes, timestamp: Optional[float] = None) -> StateUpdateEvent:
        """Validate, decode, and process a single incoming frame byte array."""
        now = timestamp if timestamp is not None else time.monotonic()
        self.frame_count += 1

        dt = now - self.last_frame_time
        if dt > 0.001:
            instant_fps = 1.0 / dt
            self.fps = 0.8 * self.fps + 0.2 * instant_fps if self.fps > 0 else instant_fps
        self.last_frame_time = now

        if len(raw_bytes) > MAX_FRAME_BYTES:
            return self._build_error_event(
                now,
                "Payload size exceeded maximum allowed limit (2.5MB).",
                StudyState.CAMERA_ERROR,
            )

        try:
            nparr = np.frombuffer(raw_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            return self._build_error_event(
                now,
                f"Image decode exception: {e}",
                StudyState.CAMERA_ERROR,
            )

        if frame is None or frame.size == 0:
            return self._build_error_event(
                now,
                "Decoded frame was empty or invalid image format.",
                StudyState.CAMERA_ERROR,
            )

        # Stride-controlled YOLO inference
        if self.frame_count % getattr(config, "YOLO_INFERENCE_STRIDE", 1) == 0 or self.frame_count <= 2:
            self.cached_yolo_info = self.yolo_service.detect(frame)

        # AI Engine arbitration
        study_state = self.focus_monitor.update_multimodal(
            bgr_frame=frame,
            yolo_detections=self.cached_yolo_info,
            camera_valid=True,
            timestamp=now,
        )

        decision: Optional[UpperBodyDecision] = self.focus_monitor.last_decision
        features: Optional[UpperBodyFeatures] = self.focus_monitor.last_features

        return self._build_event_from_decision(now, study_state, decision, features)

    def _build_event_from_decision(
        self,
        now: float,
        state: StudyState,
        decision: Optional[UpperBodyDecision],
        features: Optional[UpperBodyFeatures],
    ) -> StateUpdateEvent:
        """Assemble structured StateUpdateEvent with alert and recommendation."""
        label_text, colour = STATE_DISPLAY.get(state, (state.name, (160, 160, 160)))
        rgb_color = [colour[2], colour[1], colour[0]]

        confidence = decision.confidence if decision else 1.0
        duration = decision.duration_in_primary if decision else 0.0
        diag_reason = decision.diagnostic_reason if decision and decision.diagnostic_reason else ""

        # Extract independent observations
        obs_data = ObservationData()
        if features and features.observations:
            obs = features.observations

            act_str = "NONE"
            if hasattr(obs, "observable_study_activity"):
                act_str = getattr(obs.observable_study_activity, "details", None) or str(obs.observable_study_activity.value)

            hand_nf = False
            if hasattr(obs, "hand_near_face"):
                val = obs.hand_near_face.value
                if isinstance(val, bool):
                    hand_nf = val
                elif hasattr(val, "name"):
                    hand_nf = val.name not in ("HANDS_NOT_NEAR_FACE", "UNKNOWN")
                else:
                    hand_nf = bool(val)

            # Compute real-time derived telemetry metrics from actual signals
            focus_lvl = 0.85
            distract_lvl = 0.05
            drowsy_lvl = 0.05
            if state in (StudyState.STUDYING, StudyState.STUDYING_READING, StudyState.STUDYING_WRITING):
                focus_lvl = round(max(0.70, min(0.98, confidence)), 2)
                distract_lvl = 0.05
                drowsy_lvl = 0.05
            elif state == StudyState.RECOVERING:
                focus_lvl = 0.65
                distract_lvl = 0.20
                drowsy_lvl = 0.10
            elif state == StudyState.LOOKING_AWAY:
                focus_lvl = 0.35
                distract_lvl = 0.65
                drowsy_lvl = 0.10
            elif state == StudyState.DISTRACTED:
                focus_lvl = 0.15
                distract_lvl = 0.85
                drowsy_lvl = 0.05
            elif state == StudyState.POSSIBLE_DROWSINESS:
                focus_lvl = 0.15
                distract_lvl = 0.10
                drowsy_lvl = 0.85
            elif state in (StudyState.STUDENT_ABSENT, StudyState.FACE_OCCLUDED):
                focus_lvl = 0.0
                distract_lvl = 0.75
                drowsy_lvl = 0.0
            elif state == StudyState.INACTIVITY_WARNING:
                focus_lvl = 0.38
                distract_lvl = 0.60
                drowsy_lvl = 0.25

            atten_lvl = focus_lvl
            if features and features.ear is not None and features.head_yaw is not None and features.head_pitch is not None:
                yaw_pen = min(0.45, abs(features.head_yaw) / 50.0)
                pitch_pen = min(0.40, abs(features.head_pitch) / 60.0)
                ear_fac = min(1.0, max(0.2, features.ear / 0.26))
                atten_lvl = round(max(0.05, min(1.0, (1.0 - yaw_pen - pitch_pen) * ear_fac)), 2)

            f_box = list(features.face_box) if (features and features.face_box) else None

            obs_data = ObservationData(
                face_present=bool(obs.face_present.value) if hasattr(obs, "face_present") and hasattr(obs.face_present, "value") else False,
                face_occluded=bool(obs.face_occluded.value) if hasattr(obs, "face_occluded") and hasattr(obs.face_occluded, "value") else False,
                person_present=bool(obs.person_present.value) if hasattr(obs, "person_present") and hasattr(obs.person_present, "value") else True,
                head_direction=obs.head_direction.value.name if hasattr(getattr(obs.head_direction, "value", None), "name") else (obs.head_direction.value if hasattr(obs.head_direction, "value") else "FACING_SCREEN"),
                eye_state=obs.eye_state.value.name if hasattr(getattr(obs.eye_state, "value", None), "name") else (obs.eye_state.value if hasattr(obs.eye_state, "value") else "OPEN"),
                ear=round(features.ear, 3) if features and features.ear is not None else 0.0,
                observable_study_activity=str(act_str),
                inactivity_duration=getattr(obs, "inactivity_duration", 0.0) if not hasattr(getattr(obs, "inactivity_duration", None), "value") else float(obs.inactivity_duration.value),
                hand_near_face=hand_nf,
                camera_health=str(obs.camera_health.value) if hasattr(obs, "camera_health") and hasattr(obs.camera_health, "value") else "OK",
                detection_confidence=float(obs.detection_confidence.value) if hasattr(obs, "detection_confidence") and hasattr(obs.detection_confidence, "value") else 1.0,
                mouth_open_yawn=getattr(features, "yawn_detected", False),
                head_pitch_deg=round(features.head_pitch, 1) if features and features.head_pitch is not None else 0.0,
                head_yaw_deg=round(features.head_yaw, 1) if features and features.head_yaw is not None else 0.0,
                posture_name=features.shoulder_posture.name if features and hasattr(features, "shoulder_posture") and hasattr(features.shoulder_posture, "name") else "UPRIGHT",
                book_present=getattr(features, "book_detected", False) if features else False,
                phone_present=getattr(features, "phone_detected", False) if features else False,
                phone_status=decision.phone_status.name if decision and hasattr(decision, "phone_status") else "NONE",
                behavior_category=decision.behavior_category.name if decision and hasattr(decision, "behavior_category") else "PRODUCTIVE_STUDYING",
                laptop_present=getattr(features, "laptop_detected", False) if features else False,
                face_box=f_box,
                focus_level=focus_lvl,
                attention_level=atten_lvl,
                distraction_level=distract_lvl,
                drowsiness_level=drowsy_lvl,
            )

        # Active behaviors
        active_behaviors: List[str] = []
        if decision and decision.active_behaviors:
            active_behaviors = [b.name if hasattr(b, "name") else str(b) for b in decision.active_behaviors]

        # Alert Controller Logic
        alert = self._evaluate_alert(now, state, decision)

        # Recommendation Generation
        rec = RecommendationEngine.get_recommendation(
            state=state,
            diagnostic_reason=diag_reason,
            duration_seconds=duration,
            observations=obs_data.model_dump(),
            is_active=self.active,
        )

        # WHY DID THE AI MAKE THIS DECISION? (Part 8)
        rationale = self._build_decision_rationale(state, decision, features, alert)

        # Clean Human-Readable Activity Label (Phase 7)
        activity_label_map = {
            StudyState.STUDYING: "STUDYING",
            StudyState.STUDYING_READING: "READING",
            StudyState.STUDYING_WRITING: "WRITING",
            StudyState.LOOKING_AWAY: "LOOKING AWAY",
            StudyState.DISTRACTED: "PHONE INTERACTION",
            StudyState.POSSIBLE_DROWSINESS: "DROWSINESS",
            StudyState.INACTIVITY_WARNING: "IDLE",
            StudyState.FACE_OCCLUDED: "FACE OCCLUDED",
            StudyState.OCCLUSION_UNCERTAIN: "OCCLUSION UNCERTAIN",
            StudyState.STUDENT_ABSENT: "STUDENT ABSENT",
            StudyState.RECOVERING: "RESUMING STUDY",
            StudyState.CAMERA_ERROR: "CAMERA ERROR",
            StudyState.STUDY_ACTIVITY_UNCONFIRMED: "ACTIVITY UNCONFIRMED",
        }
        clean_activity_label = activity_label_map.get(state, state.name)
        conf_status_str = decision.confirmation_status.name if (decision and hasattr(decision, "confirmation_status")) else "CONFIRMED"

        return StateUpdateEvent(
            session_id=self.session_id,
            timestamp=now,
            frame_id=self.frame_count,
            state=state.name,
            state_display=label_text,
            state_color=rgb_color,
            confidence=confidence,
            duration_seconds=round(duration, 1),
            observations=obs_data,
            active_behaviors=active_behaviors,
            diagnostic_reason=diag_reason,
            alert=alert,
            recommendation=rec,
            decision_rationale=rationale,
            activity_label=clean_activity_label,
            confirmation_status=conf_status_str,
        )

    def _build_decision_rationale(
        self,
        state: StudyState,
        decision: Optional[UpperBodyDecision],
        features: Optional[UpperBodyFeatures],
        alert: AlertData,
    ) -> DecisionRationale:
        """Construct structured WHY DID THE AI MAKE THIS DECISION breakdown."""
        head_dir_str = "Facing Screen"
        if features and features.head_direction:
            head_dir_str = features.head_direction.name.replace("_", " ").title()

        obs_summary = f"Head direction = {head_dir_str}"
        if state == StudyState.STUDENT_ABSENT:
            obs_summary = "No person or upper-body detected in camera frame"
        elif state == StudyState.FACE_OCCLUDED:
            obs_summary = "Face landmarks completely obscured while upper body present"
        elif state == StudyState.CAMERA_ERROR:
            obs_summary = "Camera video feed interrupted, frozen, or unavailable"
        elif features and features.phone_detected:
            if getattr(features.pose_features, "phone_actively_used", False):
                obs_summary = "Active mobile phone interaction (handled + gaze directed)"
            else:
                obs_summary = "Mobile device visible on study desk (unhandled)"
        elif features and features.pose_features.repeated_head_drooping:
            obs_summary = "Head drooping repeatedly below baseline height"
        elif features and features.pose_features.repeated_head_turns:
            obs_summary = "Gaze scanning around room repeatedly"
        elif features and getattr(features, "yawn_detected", False):
            obs_summary = "Mouth opened widely (MAR > 0.48, yawn candidate)"

        ev_items = []
        if features:
            if features.phone_detected:
                ph_status_str = getattr(decision, "phone_status", "NONE")
                if hasattr(ph_status_str, "name"): ph_status_str = ph_status_str.name
                ev_items.append(f"Phone status = {ph_status_str}")

            if features.laptop_detected:
                ev_items.append("Laptop screen = Active in view")
            if features.book_detected:
                ev_items.append("Book/Notebook = Visible on desk")
            if features.hands_near_lower_border:
                ev_items.append("Desk/Keyboard activity = Active (hands at desk border)")
            elif not features.book_detected and not features.laptop_detected:
                ev_items.append("Study materials = None visible in desk region")

            if features.ear is not None:
                eye_st = "Closed" if (features.eye_state.name == "EYES_CLOSED") else "Open"
                ev_items.append(f"Eyes = {eye_st} (EAR: {features.ear:.2f})")
            else:
                ev_items.append("Eyes = Landmarks obscured")

            posture_str = features.shoulder_posture.name.replace("_", " ").title()
            ev_items.append(f"Body posture = {posture_str}")

            if features.hand_near_chin:
                ev_items.append("Thinking gesture = Hand resting at chin")
            if features.hand_near_eyes:
                ev_items.append("Fatigue gesture = Hand near eyes")

            motion_desc = "Motionless/Idle" if features.upper_body_motion < 0.01 else f"Normal motion ({features.upper_body_motion:.2f})"
            ev_items.append(f"Motion score = {motion_desc}")

        if not ev_items:
            ev_items.append("Standard seated study posture maintained")

        decision_label = state.name
        if decision:
            decision_label = decision.primary_state.name
            if decision.primary_state == BehaviorLabel.STUDYING_READING_WRITING:
                if features and features.hands_near_lower_border:
                    decision_label = "STUDYING_TYPING_WRITING"
                elif features and features.book_detected:
                    decision_label = "STUDYING_READING"

        if alert.active:
            audio_act = f"Alert eligible: {alert.name} (Priority {alert.priority})"
        else:
            audio_act = f"No alert ({alert.reason or 'Normal study activity'})"

        return DecisionRationale(
            primary_observation=obs_summary,
            additional_evidence=ev_items,
            decision=decision_label,
            audio_action=audio_act,
        )

    def _evaluate_alert(
        self,
        now: float,
        state: StudyState,
        decision: Optional[UpperBodyDecision],
    ) -> AlertData:
        """Centralized priority and cooldown alert arbitration for web client."""
        if getattr(config, "DIAGNOSTIC_MODE", False):
            self.active_alert_name = None
            self.active_alert_priority = 99
            return AlertData(active=False, reason="Safe diagnostic mode active: audio alert suppressed.")

        if state not in WEB_ALERT_CONFIG:
            self.active_alert_name = None
            self.active_alert_priority = 99
            self.last_alert_state = None
            return AlertData(active=False, reason="Clean study activity or recovery in progress.")

        if state in WEB_ALERT_CONFIG:
            audio_url, priority = WEB_ALERT_CONFIG[state]
            alert_eligible = decision.alert_eligible if decision else True

            if decision and not decision.alert_eligible:
                return AlertData(
                    active=False,
                    name=state.name,
                    priority=priority,
                    audio_file=audio_url,
                    reason=decision.alert_rejection_reason or "Duration threshold not yet satisfied.",
                )

            is_higher_priority = priority < self.active_alert_priority
            cooldown = getattr(config, "ALERT_COOLDOWN_SECONDS", 15.0)
            cooldown_expired = (now - self.last_alert_time) >= cooldown
            is_same_incident = (self.last_alert_state == state)

            # Trigger fresh alert if:
            # 1. No active alert currently tracked (fresh transition from studying)
            # 2. Or higher priority alert preemption (e.g. absent/drowsy preempts distraction)
            # 3. Or cooldown expired for a new incident
            if self.active_alert_name is None or is_higher_priority or (cooldown_expired and not is_same_incident):
                self.active_alert_name = state.name
                self.active_alert_priority = priority
                self.last_alert_time = now
                self.last_alert_state = state
                return AlertData(
                    active=True,
                    name=state.name,
                    priority=priority,
                    audio_file=audio_url,
                    reason=f"Alert triggered: {state.name} (Priority {priority})",
                )
            elif is_same_incident:
                # Active alert condition continues! Maintain alert.active=True so audio is not prematurely cancelled.
                if cooldown_expired:
                    self.last_alert_time = now
                return AlertData(
                    active=True,
                    name=state.name,
                    priority=priority,
                    audio_file=audio_url,
                    reason=f"Ongoing alert: {state.name} (Priority {priority})",
                )
            else:
                return AlertData(
                    active=False,
                    name=state.name,
                    priority=priority,
                    audio_file=audio_url,
                    reason=f"Alert suppressed: active higher alert ({self.active_alert_name}) or in cooldown.",
                )

        return AlertData(active=False, reason="Non-alert state.")

    def _build_error_event(self, now: float, error_msg: str, state: StudyState) -> StateUpdateEvent:
        """Return structured error event on frame failure."""
        label_text, colour = STATE_DISPLAY.get(state, (state.name, (180, 50, 50)))
        rgb_color = [colour[2], colour[1], colour[0]]
        rec = RecommendationEngine.get_recommendation(
            state=state,
            diagnostic_reason=error_msg,
            duration_seconds=0.0,
            is_active=self.active,
        )
        rationale = DecisionRationale(
            primary_observation=f"Camera issue: {error_msg}",
            additional_evidence=["Camera frame acquisition or decode failure"],
            decision=state.name,
            audio_action="Technical notification alert eligible" if state == StudyState.CAMERA_ERROR else "No alert",
        )
        return StateUpdateEvent(
            session_id=self.session_id,
            timestamp=now,
            frame_id=self.frame_count,
            state=state.name,
            state_display=label_text,
            state_color=rgb_color,
            confidence=1.0,
            duration_seconds=0.0,
            observations=ObservationData(camera_health="FAULT"),
            active_behaviors=[state.name],
            diagnostic_reason=error_msg,
            alert=AlertData(active=False, reason=error_msg),
            recommendation=rec,
            decision_rationale=rationale,
            activity_label="CAMERA ERROR",
            confirmation_status="UNKNOWN",
        )

    def apply_calibration(self, calibration_data: Dict[str, Any]) -> None:
        """Apply session-specific baseline head pitch/yaw and ear from calibration."""
        self.calibration_data = calibration_data
        if "baseline_ear" in calibration_data:
            try:
                self.focus_monitor.set_calibrated_ear(float(calibration_data["baseline_ear"]))
            except Exception:
                pass
        print(f"[SessionPipeline] Applied calibration for session {self.session_id}: {calibration_data}")

    def reset(self) -> None:
        """Reset temporal state machine and session metrics."""
        self.frame_count = 0
        self.start_time = time.monotonic()
        self.active_alert_name = None
        self.active_alert_priority = 99
        self.last_alert_time = 0.0
        self.focus_monitor.decision_engine.reset()

    def close(self) -> None:
        """Release session resources cleanly."""
        self.active = False
        try:
            self.focus_monitor.close()
        except Exception:
            pass
