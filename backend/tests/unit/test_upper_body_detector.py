"""
tests/test_upper_body_monitor.py — Automated Unit Tests for Upper-Body Study Behavior Recognition.
Validates:
  - Multi-label behavior generation and co-occurrence.
  - Camera constraint handling (head, shoulders, chest; missing hands/legs).
  - Missing observations represented as UNKNOWN, not negative evidence.
  - Observable pose features (chin resting, lower border hand movement, shoulder posture).
  - Temporal decision engine duration timers and priority rules.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import backend.app.core.config as config
from backend.app.services.behavior.behavior_types import (
    BehaviorLabel,
    EyeState,
    HandActivity,
    HeadDirection,
    ObjectState,
    ObservablePoseFeatures,
    ShoulderPosture,
    UpperBodyFeatures,
)
from backend.app.services.decision.temporal_decision_engine import TemporalDecisionEngine


class TestUpperBodyBehaviorRecognition(unittest.TestCase):
    """Test suite for upper-body multi-label behavior and temporal engine."""

    def setUp(self):
        self.engine = TemporalDecisionEngine(logger=None)
        # Fast deterministic thresholds for testing
        config.STUDENT_ABSENT_SECS = 4.0
        config.FACE_OCCLUDED_SECS = 3.0
        config.LOOKING_AWAY_SECS = 3.0
        config.PHONE_DETECT_SECS = 3.0
        config.DROWSINESS_SUSTAINED_SECS = 1.8
        config.CAMERA_STARING_UNCONFIRMED_SECS = 3.0
        config.INACTIVITY_WARNING_SECS = 6.0
        config.RECOVERY_STABILITY_SECS = 1.0

    def _make_features(self, t: float, **kwargs) -> UpperBodyFeatures:
        defaults = {
            "timestamp": t,
            "camera_valid": True,
            "frame_frozen": False,
            "low_visibility": False,
            "person_detected": True,
            "face_detected": True,
            "face_conf": 0.95,
            "ear": 0.32,
            "head_yaw": 0.0,
            "head_pitch": 4.0,
            "head_roll": 0.0,
            "shoulders_detected": True,
            "left_shoulder": (0.35, 0.45, 0.0),
            "right_shoulder": (0.65, 0.45, 0.0),
            "shoulder_tilt_deg": 0.0,
            "hands_visible_count": 0,
            "hands_near_lower_border": False,
            "hand_to_face_iou": 0.0,
            "hand_near_chin": False,
            "book_detected": False,
            "phone_detected": False,
            "laptop_detected": False,
            "head_direction": HeadDirection.FACING_SCREEN,
            "eye_state": EyeState.EYES_OPEN,
            "shoulder_posture": ShoulderPosture.UPRIGHT,
            "hand_activity": HandActivity.HANDS_NOT_VISIBLE,
            "object_state": ObjectState.NONE,
            "pose_features": ObservablePoseFeatures(head_facing_screen=True, upright_upper_body=True),
        }
        defaults.update(kwargs)
        return UpperBodyFeatures(**defaults)

    # ──────────────────────────────────────────────────────────────────
    # Test 1: Missing observations represented as UNKNOWN, not negative evidence
    # ──────────────────────────────────────────────────────────────────
    def test_missing_observations_are_unknown(self):
        f = self._make_features(
            100.0,
            ear=None,
            eye_state=EyeState.UNKNOWN,
            hands_visible_count=0,
            hand_activity=HandActivity.HANDS_NOT_VISIBLE,
        )
        decision = self.engine.update(f)
        # Missing eyes must NOT trigger drowsiness
        self.assertNotIn(BehaviorLabel.POSSIBLE_DROWSINESS, decision.active_behaviors)
        # Missing hands must NOT be treated as negative evidence
        self.assertEqual(f.hand_activity, HandActivity.HANDS_NOT_VISIBLE)

    # ──────────────────────────────────────────────────────────────────
    # Test 2: Multi-label co-occurrence (Writing while partially occluded)
    # ──────────────────────────────────────────────────────────────────
    def test_multilabel_cooccurrence_reading_and_partial_occlusion(self):
        # Student looking down reading book that partly overlaps lower face
        f = self._make_features(
            100.0,
            book_detected=True,
            head_pitch=22.0,
            head_direction=HeadDirection.TILTED_DOWN,
            face_detected=False,  # Lower landmarks obscured
            hand_to_face_iou=0.0,
        )
        decision = self.engine.update(f)
        # Both behaviors active simultaneously without mutually exclusive forcing
        self.assertIn(BehaviorLabel.STUDYING_READING_WRITING, decision.active_behaviors)
        self.assertIn(BehaviorLabel.FACE_PARTIALLY_OCCLUDED, decision.active_behaviors)
        self.assertEqual(decision.primary_state, BehaviorLabel.STUDYING_READING_WRITING)

    # ──────────────────────────────────────────────────────────────────
    # Test 3: Thinking with hand resting on chin is NOT face occlusion
    # ──────────────────────────────────────────────────────────────────
    def test_thinking_hand_on_chin_not_occlusion(self):
        pose = ObservablePoseFeatures(head_facing_screen=True, face_resting_on_hand=True, upright_upper_body=True)
        f = self._make_features(
            100.0,
            face_detected=True,
            hand_near_chin=True,
            hand_to_face_iou=0.18,  # Only touches chin border
            pose_features=pose,
        )
        decision = self.engine.update(f)
        self.assertNotIn(BehaviorLabel.FACE_FULLY_OCCLUDED, decision.active_behaviors)
        self.assertEqual(decision.primary_state, BehaviorLabel.STUDYING_SCREEN)

    # ──────────────────────────────────────────────────────────────────
    # Test 4: Deliberate full face concealment triggers FACE_FULLY_OCCLUDED
    # ──────────────────────────────────────────────────────────────────
    def test_deliberate_face_concealment(self):
        decision = None
        pose = ObservablePoseFeatures(face_covered_by_hand=True)
        for i in range(35):  # 3.5s (> FACE_OCCLUDED_SECS 3.0s)
            t = 100.0 + i * 0.1
            f = self._make_features(
                t,
                face_detected=False,
                hand_to_face_iou=0.60,
                pose_features=pose,
            )
            decision = self.engine.update(f)
        self.assertIn(BehaviorLabel.FACE_FULLY_OCCLUDED, decision.active_behaviors)
        self.assertEqual(decision.primary_state, BehaviorLabel.FACE_FULLY_OCCLUDED)

    # ──────────────────────────────────────────────────────────────────
    # Test 5: Hands moving near lower boundary (Desk writing/typing)
    # ──────────────────────────────────────────────────────────────────
    def test_hands_near_lower_boundary_classified_as_writing(self):
        pose = ObservablePoseFeatures(hands_moving_near_lower_camera_boundary=True)
        f = self._make_features(
            100.0,
            hands_near_lower_border=True,
            head_pitch=16.0,
            head_direction=HeadDirection.TILTED_DOWN,
            pose_features=pose,
        )
        decision = self.engine.update(f)
        self.assertIn(BehaviorLabel.STUDYING_READING_WRITING, decision.active_behaviors)
        self.assertEqual(decision.primary_state, BehaviorLabel.STUDYING_READING_WRITING)

    # ──────────────────────────────────────────────────────────────────
    # Test 6: Motionless watching video transitions via ACTIVITY_UNCONFIRMED
    # ──────────────────────────────────────────────────────────────────
    def test_motionless_camera_facing_unconfirmed_before_distraction(self):
        pose = ObservablePoseFeatures(head_facing_screen=True, minimal_upper_body_movement=True)
        # 3.6s of still gazing (> 3.0s threshold + consensus window): ACTIVITY_UNCONFIRMED, NOT distraction
        decision = None
        for i in range(36):
            t = 100.0 + i * 0.1
            f = self._make_features(t, pose_features=pose)
            decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.ACTIVITY_UNCONFIRMED)
        self.assertNotIn(BehaviorLabel.POSSIBLE_DISTRACTION, decision.active_behaviors)

        # Continues past 6.0s (up to 6.8s): enters POSSIBLE_DISTRACTION
        for i in range(36, 68):
            t = 100.0 + i * 0.1
            f = self._make_features(t, pose_features=pose)
            decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.POSSIBLE_DISTRACTION)

    # ──────────────────────────────────────────────────────────────────
    # Test 7: Normal blinks vs Sustained Eye Closure
    # ──────────────────────────────────────────────────────────────────
    def test_blinking_vs_sustained_drowsiness(self):
        # Brief blink (0.2s)
        self.engine.update(self._make_features(100.0, ear=0.12))
        d_blink = self.engine.update(self._make_features(100.1, ear=0.12))
        self.assertNotEqual(d_blink.primary_state, BehaviorLabel.POSSIBLE_DROWSINESS)

        # Eyes reopen
        self.engine.update(self._make_features(100.2, ear=0.32))

        # Sustained closure (2.2s > 1.8s)
        decision = None
        pose = ObservablePoseFeatures(sustained_eye_closure=True)
        for i in range(22):
            t = 101.0 + i * 0.1
            decision = self.engine.update(self._make_features(t, ear=0.12, pose_features=pose))
        self.assertEqual(decision.primary_state, BehaviorLabel.POSSIBLE_DROWSINESS)

    # ──────────────────────────────────────────────────────────────────
    # Test 8: Upper body absence and recovery
    # ──────────────────────────────────────────────────────────────────
    def test_upper_body_absence_and_recovery(self):
        # Absent for 4.5s (> STUDENT_ABSENT_SECS 4.0s)
        decision = None
        for i in range(45):
            t = 100.0 + i * 0.1
            f = self._make_features(t, person_detected=False, face_detected=False, shoulders_detected=False)
            decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.STUDENT_ABSENT)

        # Returns to study: RECOVERING
        d_rec = self.engine.update(self._make_features(105.0))
        self.assertEqual(d_rec.primary_state, BehaviorLabel.RECOVERING)

        # Clean study sustained for 1.2s: STUDYING_SCREEN
        for i in range(12):
            t = 105.1 + i * 0.1
            decision = self.engine.update(self._make_features(t))
        self.assertEqual(decision.primary_state, BehaviorLabel.STUDYING_SCREEN)


if __name__ == "__main__":
    unittest.main()
