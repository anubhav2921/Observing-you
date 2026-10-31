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


# Canonical face mesh drawing indices matching reference overlay
_FACE_OVAL_IDX = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109, 10]
_LIPS_OUTER_IDX = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185, 61]
_LIPS_INNER_IDX = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415, 310, 311, 312, 13, 82, 81, 80, 191, 78]
_LEFT_EYE_IDX = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246, 33]
_LEFT_EYEBROW_IDX = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
_RIGHT_EYE_IDX = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398, 362]
_RIGHT_EYEBROW_IDX = [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]
_LEFT_IRIS_IDX = [469, 470, 471, 472, 469]
_RIGHT_IRIS_IDX = [474, 475, 476, 477, 474]
_POSE_CONNECTIONS = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24)]
_HAND_FINGERS = [
    [0, 1, 2, 3, 4],
    [0, 5, 6, 7, 8],
    [0, 9, 10, 11, 12],
    [0, 13, 14, 15, 16],
    [0, 17, 18, 19, 20],
    [5, 9, 13, 17],
]


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
        """Render upper-body landmarks matching visual reference (face mesh, eye contours, irises, lips, pose, hands)."""
        if not getattr(config, "SHOW_LANDMARKS", True) or bgr_frame is None:
            return
        try:
            h, w = bgr_frame.shape[:2]
            f = self.last_features
            if f is None:
                return

            # 1. Pose skeleton (Cyan lines and joints)
            if f.pose_landmarks_raw and len(f.pose_landmarks_raw) >= 25:
                p_pts = [(int(p[0] * w), int(p[1] * h)) for p in f.pose_landmarks_raw]
                for idx1, idx2 in _POSE_CONNECTIONS:
                    if 0 <= idx1 < len(p_pts) and 0 <= idx2 < len(p_pts):
                        cv2.line(bgr_frame, p_pts[idx1], p_pts[idx2], (255, 200, 0), 2, cv2.LINE_AA)
                for idx in (11, 12, 13, 14, 15, 16, 23, 24):
                    if 0 <= idx < len(p_pts):
                        cv2.circle(bgr_frame, p_pts[idx], 4, (0, 255, 255), -1)

            # 2. Hand skeletons (Yellow lines and orange joint dots)
            if f.hand_landmarks_raw:
                for h_lm in f.hand_landmarks_raw:
                    if len(h_lm) >= 21:
                        h_pts = [(int(p[0] * w), int(p[1] * h)) for p in h_lm]
                        for finger in _HAND_FINGERS:
                            for i in range(len(finger) - 1):
                                if finger[i] < len(h_pts) and finger[i+1] < len(h_pts):
                                    cv2.line(bgr_frame, h_pts[finger[i]], h_pts[finger[i+1]], (0, 230, 255), 2, cv2.LINE_AA)
                        for pt in h_pts:
                            cv2.circle(bgr_frame, pt, 2, (0, 180, 255), -1)

            # 3. Face Mesh & Detailed Facial Contours (Matching Visual Reference)
            if f.face_landmarks_raw and len(f.face_landmarks_raw) >= 468:
                lm = f.face_landmarks_raw
                pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in lm[:468]], dtype=np.int32)

                # Delaunay wireframe (thin grey lines)
                subdiv = cv2.Subdiv2D((0, 0, w, h))
                for p in pts:
                    subdiv.insert((float(p[0]), float(p[1])))
                triangles = subdiv.getTriangleList()
                hull = cv2.convexHull(pts)

                for t in triangles:
                    pt1 = (int(t[0]), int(t[1]))
                    pt2 = (int(t[2]), int(t[3]))
                    pt3 = (int(t[4]), int(t[5]))
                    if (cv2.pointPolygonTest(hull, (float(t[0]), float(t[1])), False) >= 0 and
                        cv2.pointPolygonTest(hull, (float(t[2]), float(t[3])), False) >= 0 and
                        cv2.pointPolygonTest(hull, (float(t[4]), float(t[5])), False) >= 0):
                        cv2.line(bgr_frame, pt1, pt2, (150, 150, 150), 1, cv2.LINE_AA)
                        cv2.line(bgr_frame, pt2, pt3, (150, 150, 150), 1, cv2.LINE_AA)
                        cv2.line(bgr_frame, pt3, pt1, (150, 150, 150), 1, cv2.LINE_AA)

                # Face oval (smooth white line)
                oval_pts = np.array([pts[i] for i in _FACE_OVAL_IDX if i < len(pts)], dtype=np.int32)
                if len(oval_pts) > 0:
                    cv2.polylines(bgr_frame, [oval_pts], False, (245, 245, 245), 2, cv2.LINE_AA)

                # Lips outer & inner (smooth white line)
                outer_pts = np.array([pts[i] for i in _LIPS_OUTER_IDX if i < len(pts)], dtype=np.int32)
                inner_pts = np.array([pts[i] for i in _LIPS_INNER_IDX if i < len(pts)], dtype=np.int32)
                if len(outer_pts) > 0:
                    cv2.polylines(bgr_frame, [outer_pts], True, (245, 245, 245), 2, cv2.LINE_AA)
                if len(inner_pts) > 0:
                    cv2.polylines(bgr_frame, [inner_pts], True, (245, 245, 245), 2, cv2.LINE_AA)

                # Left eye & eyebrow (vivid green line)
                l_eye_pts = np.array([pts[i] for i in _LEFT_EYE_IDX if i < len(pts)], dtype=np.int32)
                l_brow_pts = np.array([pts[i] for i in _LEFT_EYEBROW_IDX if i < len(pts)], dtype=np.int32)
                if len(l_eye_pts) > 0:
                    cv2.polylines(bgr_frame, [l_eye_pts], True, (0, 230, 80), 2, cv2.LINE_AA)
                if len(l_brow_pts) > 0:
                    cv2.polylines(bgr_frame, [l_brow_pts], False, (0, 230, 80), 2, cv2.LINE_AA)

                # Right eye & eyebrow (vivid red line)
                r_eye_pts = np.array([pts[i] for i in _RIGHT_EYE_IDX if i < len(pts)], dtype=np.int32)
                r_brow_pts = np.array([pts[i] for i in _RIGHT_EYEBROW_IDX if i < len(pts)], dtype=np.int32)
                if len(r_eye_pts) > 0:
                    cv2.polylines(bgr_frame, [r_eye_pts], True, (0, 50, 240), 2, cv2.LINE_AA)
                if len(r_brow_pts) > 0:
                    cv2.polylines(bgr_frame, [r_brow_pts], False, (0, 50, 240), 2, cv2.LINE_AA)

                # Iris diamonds (green left, red right)
                if len(lm) >= 478:
                    all_pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in lm], dtype=np.int32)
                    l_iris_pts = np.array([all_pts[i] for i in _LEFT_IRIS_IDX if i < len(all_pts)], dtype=np.int32)
                    r_iris_pts = np.array([all_pts[i] for i in _RIGHT_IRIS_IDX if i < len(all_pts)], dtype=np.int32)
                    if len(l_iris_pts) > 0:
                        cv2.polylines(bgr_frame, [l_iris_pts], True, (0, 230, 80), 2, cv2.LINE_AA)
                    if len(r_iris_pts) > 0:
                        cv2.polylines(bgr_frame, [r_iris_pts], True, (0, 50, 240), 2, cv2.LINE_AA)
                    cv2.circle(bgr_frame, tuple(all_pts[468]), 2, (0, 230, 80), -1)
                    cv2.circle(bgr_frame, tuple(all_pts[473]), 2, (0, 50, 240), -1)

            elif f.face_box is not None:
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
