"""
backend/app/services/detection/focus_monitor.py — Upper-Body Study Behavior Monitor.
Orchestrates UpperBodyDetector and TemporalDecisionEngine into authoritative StudyState.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import cv2
import numpy as np

import backend.app.core.config as config
from backend.app.core.logging import StructuredLogger
from backend.app.services.behavior.behavior_types import (
    BehaviorLabel,
    EyeState,
    HandActivity,
    HeadDirection,
    ObjectState,
    ObservablePoseFeatures,
    ShoulderPosture,
    UpperBodyDecision,
    UpperBodyFeatures,
)
from backend.app.services.decision.state_machine import (
    ALERT_STATES,
    STATE_DISPLAY,
    STATE_RESPONSES,
    StudyState,
)
from backend.app.services.decision.temporal_decision_engine import (
    ALERT_BEHAVIORS,
    TemporalDecisionEngine,
)
from backend.app.services.detection.upper_body_detector import UpperBodyDetector

# Aliases for backward compatibility
FocusState = StudyState

DISTRACTION_STATES: set[StudyState] = {
    StudyState.LOOKING_AWAY,
    StudyState.DISTRACTED,
    StudyState.FACE_OCCLUDED,
    StudyState.STUDENT_ABSENT,
    StudyState.INACTIVITY_WARNING,
    StudyState.CAMERA_ERROR,
    StudyState.OCCLUSION_UNCERTAIN,
}

_BEHAVIOR_TO_STUDY_STATE: Dict[BehaviorLabel, StudyState] = {
    BehaviorLabel.STUDYING_SCREEN:          StudyState.STUDYING,
    BehaviorLabel.STUDYING_READING_WRITING: StudyState.STUDYING_READING,
    BehaviorLabel.POSSIBLE_DISTRACTION:     StudyState.DISTRACTED,
    BehaviorLabel.LOOKING_AWAY:             StudyState.LOOKING_AWAY,
    BehaviorLabel.INACTIVITY_WARNING:       StudyState.INACTIVITY_WARNING,
    BehaviorLabel.OFF_TASK_CANDIDATE:       StudyState.LOOKING_AWAY,
    BehaviorLabel.ACTIVITY_UNCONFIRMED:     StudyState.STUDY_ACTIVITY_UNCONFIRMED,
    BehaviorLabel.FACE_PARTIALLY_OCCLUDED:  StudyState.OCCLUSION_UNCERTAIN,
    BehaviorLabel.FACE_FULLY_OCCLUDED:      StudyState.FACE_OCCLUDED,
    BehaviorLabel.POSSIBLE_DROWSINESS:      StudyState.POSSIBLE_DROWSINESS,
    BehaviorLabel.STUDENT_ABSENT:           StudyState.STUDENT_ABSENT,
    BehaviorLabel.CAMERA_ERROR:             StudyState.CAMERA_ERROR,
    BehaviorLabel.LOW_VISIBILITY:           StudyState.LOW_VISIBILITY,
    BehaviorLabel.RECOVERING:               StudyState.RECOVERING,
}


class FocusMonitor:
    """
    Upper-body focus monitor integrating facial landmarks, shoulder orientation,
    hand interaction, multi-label behaviors, and temporal decision engine.
    """

    def __init__(self, logger: Optional[StructuredLogger] = None) -> None:
        self.logger = logger
        self.detector = UpperBodyDetector()
        self.decision_engine = TemporalDecisionEngine(logger=logger)
        self._frame_count = 0

        self.last_decision: Optional[UpperBodyDecision] = None
        self.last_features: Optional[UpperBodyFeatures] = None

        # Diagnostic attributes
        self.last_ear: float = 0.0
        self.last_yaw: Optional[float] = None
        self.last_pitch: Optional[float] = None
        self.last_confidence: float = 1.0

        self.last_active_behaviors: Set[BehaviorLabel] = set()
        self.last_pose_features: ObservablePoseFeatures = ObservablePoseFeatures()
        self.last_shoulder_tilt: Optional[float] = None

    def reset(self) -> None:
        """Reset decision engine and cached observation telemetry."""
        self._frame_count = 0
        self.last_decision = None
        self.last_features = None
        self.last_ear = 0.0
        self.last_yaw = None
        self.last_pitch = None
        self.last_confidence = 1.0
        self.last_active_behaviors.clear()
        self.last_pose_features = ObservablePoseFeatures()
        self.decision_engine.reset()

    def set_calibrated_ear(self, ear: float) -> None:
        """Pass calibrated baseline open EAR to detector."""
        self.detector.set_calibrated_ear(ear)

    def update_multimodal(
        self,
        bgr_frame: Optional[np.ndarray],
        yolo_detections: Optional[Dict[str, Any]] = None,
        camera_valid: bool = True,
        timestamp: Optional[float] = None,
    ) -> StudyState:
        """Extract features and arbitrate authoritative decision."""
        now = timestamp if timestamp is not None else time.monotonic()

        # Step 1: Feature Extraction
        features = self.detector.extract_features(
            bgr_frame=bgr_frame,
            yolo_info=yolo_detections,
            camera_valid=camera_valid,
            timestamp=now,
        )
        self.last_features = features

        # Step 2: Temporal Decision Engine
        decision = self.decision_engine.update(features)
        self.last_decision = decision

        # Diagnostics
        self.last_ear = features.ear if features.ear is not None else 0.0
        self.last_yaw = features.head_yaw
        self.last_pitch = features.head_pitch
        self.last_confidence = decision.confidence
        self.last_active_behaviors = decision.active_behaviors
        self.last_pose_features = features.pose_features
        self.last_shoulder_tilt = features.shoulder_tilt_deg

        # Map to StudyState
        if decision.primary_state == BehaviorLabel.POSSIBLE_DISTRACTION:
            trig_lower = decision.trigger_condition.lower()
            if "phone" in trig_lower:
                study_state = StudyState.DISTRACTED
            elif "away" in trig_lower or "room" in trig_lower:
                study_state = StudyState.LOOKING_AWAY
            elif "inactiv" in trig_lower or "idle" in trig_lower or "staring" in trig_lower or "motionless" in trig_lower:
                study_state = StudyState.INACTIVITY_WARNING
            else:
                study_state = StudyState.DISTRACTED
        else:
            study_state = _BEHAVIOR_TO_STUDY_STATE.get(decision.primary_state, StudyState.STUDYING)

        # Logging
        self._frame_count += 1
        if self.logger and (self._frame_count % 30 == 0 or decision.transitioned or decision.primary_state in ALERT_BEHAVIORS):
            cam_health = "OK" if features.camera_valid and not features.frame_frozen and not features.low_visibility and not getattr(features, "inference_error", False) else "FAULT"
            self.logger.log_diagnostic(
                frame_idx=self._frame_count,
                timestamp=now,
                camera_health=cam_health,
                state=decision.primary_state.name,
                duration=decision.duration_in_primary,
                confidence=decision.confidence,
                observations=features.observations.to_dict() if features.observations else {},
                alert_eligible=decision.alert_eligible,
                alert_rejection_reason=decision.alert_rejection_reason,
                raw_predictions={
                    "timestamp": round(now, 3),
                    "left_ear": round(features.left_ear, 3) if features.left_ear is not None else None,
                    "right_ear": round(features.right_ear, 3) if features.right_ear is not None else None,
                    "avg_ear": round(features.ear, 3) if features.ear is not None else None,
                    "face_visibility": features.face_detected,
                    "head_yaw": round(features.head_yaw, 1) if features.head_yaw is not None else None,
                    "head_pitch": round(features.head_pitch, 1) if features.head_pitch is not None else None,
                    "hand_detection": features.hands_visible_count > 0,
                    "phone_detection": features.phone_detected,
                    "raw_activity": decision.trigger_condition,
                    "confirmed_activity": decision.primary_state.name,
                    "duration": round(decision.duration_in_primary, 2),
                    "audio_eligibility": decision.alert_eligible,
                    "audio_trigger_reason": decision.diagnostic_reason,
                    "motion": round(features.upper_body_motion, 4),
                    "book": features.book_detected,
                },
            )

        return study_state

    def update(self, bgr_frame, phone_detected: bool = False) -> StudyState:
        """Legacy interface wrapper."""
        yolo_info = {
            "person_detected": True,
            "person_conf": 0.90,
            "phone_detected": phone_detected,
            "book_detected": False,
        }
        return self.update_multimodal(bgr_frame, yolo_detections=yolo_info)

    def draw_landmarks(self, bgr_frame: np.ndarray) -> None:
        """Render upper-body landmarks (face mesh, shoulder line, chest center, hands)."""
        if not getattr(config, "SHOW_LANDMARKS", True) or bgr_frame is None:
            return
        try:
            h, w = bgr_frame.shape[:2]
            f = self.last_features
            if f is None:
                return

            if f.shoulders_detected and f.left_shoulder is not None and f.right_shoulder is not None:
                lx, ly = int(f.left_shoulder[0] * w), int(f.left_shoulder[1] * h)
                rx, ry = int(f.right_shoulder[0] * w), int(f.right_shoulder[1] * h)
                cv2.line(bgr_frame, (lx, ly), (rx, ry), (255, 180, 0), 3)
                cv2.circle(bgr_frame, (lx, ly), 5, (0, 255, 255), -1)
                cv2.circle(bgr_frame, (rx, ry), 5, (0, 255, 255), -1)

            if f.face_box is not None:
                fx1, fy1, fx2, fy2 = f.face_box
                cv2.rectangle(bgr_frame, (fx1, fy1), (fx2, fy2), (0, 255, 180), 1)
        except Exception:
            pass

    def process_frame(
        self,
        bgr_frame: Optional[np.ndarray],
        timestamp: Optional[float] = None,
        yolo_detections: Optional[Dict[str, Any]] = None,
    ) -> Tuple[StudyState, float]:
        """Process a frame and return (state, duration_in_state)."""
        now = timestamp if timestamp is not None else time.monotonic()
        state = self.update_multimodal(
            bgr_frame=bgr_frame,
            yolo_detections=yolo_detections,
            camera_valid=True,
            timestamp=now,
        )
        duration = self.last_decision.duration_in_primary if self.last_decision else 0.0
        return state, duration

    @property
    def last_observation(self) -> Optional[IndependentObservations]:
        """Return latest independent multi-modal observations."""
        if self.last_features and self.last_features.observations:
            return self.last_features.observations
        return None

    @property
    def available(self) -> bool:
        return True

    def close(self) -> None:
        """Release detector resources cleanly."""
        self.detector.close()
