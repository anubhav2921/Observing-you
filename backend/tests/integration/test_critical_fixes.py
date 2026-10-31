"""
tests/test_critical_fixes.py — Automated Regression Test Suite
Validates all 16 required regression tests (Section 8) and explicit scenarios (Section 3).
Operates purely with mocked detector signals and features — no physical webcam required.
"""

from __future__ import annotations

import os
import sys
import time
import unittest

# Ensure parent directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import backend.app.core.config as config
from backend.app.services.audio.audio_alerts import CentralAudioManager
from backend.app.services.behavior.behavior_types import (
    BehaviorLabel,
    EyeState,
    HandActivity,
    HeadDirection,
    ObservablePoseFeatures,
    ShoulderPosture,
    UpperBodyFeatures,
)
from backend.app.services.detection.focus_monitor import FocusMonitor, StudyState
from backend.app.services.decision.state_machine import DetectorSignals, StudyStateMachine
from backend.app.services.decision.temporal_decision_engine import TemporalDecisionEngine


class TestCriticalFixesRegressionSuite(unittest.TestCase):
    """
    Comprehensive regression test suite for all 16 scenarios required by Section 8,
    plus specific edge-case scenarios from Section 3 (A, B, C, D).
    """

    def setUp(self):
        # Configure thresholds for deterministic unit test execution
        config.STUDENT_ABSENT_SECS = 4.0
        config.FACE_OCCLUDED_SECS = 3.0
        config.LOOKING_AWAY_SECS = 3.0
        config.PHONE_DETECT_SECS = 3.0
        config.DROWSINESS_SUSTAINED_SECS = 1.8
        config.CAMERA_STARING_UNCONFIRMED_SECS = 3.0
        config.INACTIVITY_WARNING_SECS = 6.0
        config.RECOVERY_STABILITY_SECS = 1.0
        config.ALERT_COOLDOWN_SECONDS = 5.0
        config.AUDIO_ENABLED = True
        config.DISTRACTION_ALERT_ENABLED = True
        config.SLEEPINESS_ALERT_ENABLED = True
        config.CAMERA_ERROR_ALERT_ENABLED = True
        config.OCCLUSION_ALERT_ENABLED = True

        self.engine = TemporalDecisionEngine(logger=None)
        self.sm = StudyStateMachine(logger=None)

    def _make_features(self, t: float, **kwargs) -> UpperBodyFeatures:
        """Helper to create an UpperBodyFeatures object with sensible study defaults."""
        defaults = {
            "timestamp": t,
            "camera_valid": True,
            "frame_frozen": False,
            "low_visibility": False,
            "person_detected": True,
            "person_conf": 0.95,
            "face_detected": True,
            "face_conf": 0.95,
            "ear": 0.32,
            "head_yaw": 0.0,
            "head_pitch": 4.0,
            "head_roll": 0.0,
            "shoulders_detected": True,
            "shoulder_posture": ShoulderPosture.UPRIGHT,
            "head_direction": HeadDirection.FACING_SCREEN,
            "eye_state": EyeState.EYES_OPEN,
            "hand_activity": HandActivity.UNKNOWN,
            "phone_detected": False,
            "book_detected": False,
            "laptop_detected": False,
            "upper_body_motion": 0.015,
        }
        defaults.update(kwargs)
        if "pose_features" not in defaults:
            defaults["pose_features"] = ObservablePoseFeatures(
                head_facing_screen=(defaults["head_direction"] == HeadDirection.FACING_SCREEN),
                upright_upper_body=(defaults["shoulder_posture"] == ShoulderPosture.UPRIGHT),
            )
        return UpperBodyFeatures(**defaults)

    # ──────────────────────────────────────────────────────────────────
    # 1. Student is inactive for longer than the threshold
    # ──────────────────────────────────────────────────────────────────
    def test_01_student_inactive_longer_than_threshold(self):
        pose = ObservablePoseFeatures(head_facing_screen=True, minimal_upper_body_movement=True)
        decision = None
        for i in range(70):  # 7.0s > INACTIVITY_WARNING_SECS 6.0s
            t = 100.0 + i * 0.1
            f = self._make_features(t, upper_body_motion=0.002, pose_features=pose)
            decision = self.engine.update(f)

        self.assertEqual(decision.primary_state, BehaviorLabel.POSSIBLE_DISTRACTION)
        self.assertIn("inactivity", decision.trigger_condition.lower())
        self.assertTrue(decision.alert_eligible)

    # ──────────────────────────────────────────────────────────────────
    # 2. Student stares at the camera without observable study activity
    # ──────────────────────────────────────────────────────────────────
    def test_02_student_stares_at_camera_without_observable_study_activity(self):
        pose = ObservablePoseFeatures(head_facing_screen=True, minimal_upper_body_movement=True)
        # Phase 1: 3.5s -> ACTIVITY_UNCONFIRMED
        for i in range(35):
            t = 100.0 + i * 0.1
            f = self._make_features(t, upper_body_motion=0.001, pose_features=pose)
            d1 = self.engine.update(f)
        self.assertEqual(d1.primary_state, BehaviorLabel.ACTIVITY_UNCONFIRMED)

        # Phase 2: Continues past 6.0s -> triggers warning alert
        d2 = None
        for i in range(35, 70):
            t = 100.0 + i * 0.1
            f = self._make_features(t, upper_body_motion=0.001, pose_features=pose)
            d2 = self.engine.update(f)
        self.assertEqual(d2.primary_state, BehaviorLabel.POSSIBLE_DISTRACTION)
        self.assertTrue(d2.alert_eligible)

    # ──────────────────────────────────────────────────────────────────
    # 3. Student uses a phone with off-task evidence
    # ──────────────────────────────────────────────────────────────────
    def test_03_student_uses_phone_with_off_task_evidence(self):
        decision = None
        for i in range(35):  # 3.5s > PHONE_DETECT_SECS 3.0s
            t = 100.0 + i * 0.1
            f = self._make_features(t, phone_detected=True)
            decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.POSSIBLE_DISTRACTION)
        self.assertIn("cell phone", decision.trigger_condition.lower())

    # ──────────────────────────────────────────────────────────────────
    # 4. Student looks away briefly
    # ──────────────────────────────────────────────────────────────────
    def test_04_student_looks_away_briefly(self):
        # Initial studying
        self.engine.update(self._make_features(100.0, head_yaw=0.0))
        # Look away for 1.2s (< LOOKING_AWAY_SECS 3.0s)
        decision = None
        for i in range(12):
            t = 101.0 + i * 0.1
            f = self._make_features(t, head_yaw=32.0, head_direction=HeadDirection.TURNED_RIGHT)
            decision = self.engine.update(f)
        # Must NOT trigger distraction yet
        self.assertNotEqual(decision.primary_state, BehaviorLabel.POSSIBLE_DISTRACTION)
        self.assertEqual(decision.primary_state, BehaviorLabel.STUDYING_SCREEN)

    # ──────────────────────────────────────────────────────────────────
    # 5. Student reads with their face partly covered
    # ──────────────────────────────────────────────────────────────────
    def test_05_student_reads_face_partly_covered(self):
        decision = None
        for i in range(40):
            t = 100.0 + i * 0.1
            # Book detected, downward reading pitch, face landmarks missing
            f = self._make_features(t, face_detected=False, book_detected=True, head_pitch=20.0)
            decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.STUDYING_READING_WRITING)
        self.assertFalse(decision.alert_eligible)

    # ──────────────────────────────────────────────────────────────────
    # 6. Student's face is fully occluded for several seconds
    # ──────────────────────────────────────────────────────────────────
    def test_06_student_face_fully_occluded_several_seconds(self):
        pose = ObservablePoseFeatures(face_covered_by_hand=True)
        decision = None
        for i in range(35):  # 3.5s > FACE_OCCLUDED_SECS 3.0s
            t = 100.0 + i * 0.1
            f = self._make_features(t, face_detected=False, hand_to_face_iou=0.65, pose_features=pose)
            decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.FACE_FULLY_OCCLUDED)
        self.assertTrue(decision.alert_eligible)

    # ──────────────────────────────────────────────────────────────────
    # 7. Student leaves the frame
    # ──────────────────────────────────────────────────────────────────
    def test_07_student_leaves_the_frame(self):
        decision = None
        for i in range(45):  # 4.5s > STUDENT_ABSENT_SECS 4.0s
            t = 100.0 + i * 0.1
            f = self._make_features(t, person_detected=False, shoulders_detected=False, face_detected=False)
            decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.STUDENT_ABSENT)

    # ──────────────────────────────────────────────────────────────────
    # 8. Student blinks normally
    # ──────────────────────────────────────────────────────────────────
    def test_08_student_blinks_normally(self):
        t = 100.0
        # 0.2s closed
        for _ in range(2):
            t += 0.1
            f = self._make_features(t, ear=0.10)
            d = self.engine.update(f)
            self.assertNotEqual(d.primary_state, BehaviorLabel.POSSIBLE_DROWSINESS)
        # 0.5s open
        for _ in range(5):
            t += 0.1
            f = self._make_features(t, ear=0.32)
            d = self.engine.update(f)
            self.assertEqual(d.primary_state, BehaviorLabel.STUDYING_SCREEN)

    # ──────────────────────────────────────────────────────────────────
    # 9. Sustained drowsiness-like signals occur
    # ──────────────────────────────────────────────────────────────────
    def test_09_sustained_drowsiness_signals_occur(self):
        decision = None
        for i in range(22):  # 2.2s > DROWSINESS_SUSTAINED_SECS 1.8s
            t = 100.0 + i * 0.1
            f = self._make_features(t, ear=0.12)
            decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.POSSIBLE_DROWSINESS)
        self.assertTrue(decision.alert_eligible)

    # ──────────────────────────────────────────────────────────────────
    # 10. Camera becomes unavailable
    # ──────────────────────────────────────────────────────────────────
    def test_10_camera_becomes_unavailable(self):
        f = self._make_features(100.0, camera_valid=False)
        decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.CAMERA_ERROR)
        self.assertEqual(decision.confidence, 0.98)

    # ──────────────────────────────────────────────────────────────────
    # 11. Inference throws an exception
    # ──────────────────────────────────────────────────────────────────
    def test_11_inference_throws_exception(self):
        # Simulate model inference error flag
        f = self._make_features(100.0, inference_error=True)
        decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.CAMERA_ERROR)
        self.assertIn("error", decision.trigger_condition.lower())

    # ──────────────────────────────────────────────────────────────────
    # 12. Detection confidence falls below configured threshold
    # ──────────────────────────────────────────────────────────────────
    def test_12_detection_confidence_below_threshold(self):
        # When person detection is below confidence and landmarks uncertain
        f = self._make_features(100.0, person_detected=False, shoulders_detected=False, face_detected=False)
        d = self.engine.update(f)
        # Initially enters ACTIVITY_UNCONFIRMED awaiting full duration
        self.assertEqual(d.primary_state, BehaviorLabel.ACTIVITY_UNCONFIRMED)
        self.assertFalse(d.alert_eligible)

    # ──────────────────────────────────────────────────────────────────
    # 13. A condition persists while detections fluctuate
    # ──────────────────────────────────────────────────────────────────
    def test_13_condition_persists_while_detections_fluctuate(self):
        # Gaze turned away with minor yaw fluctuation (e.g. 26 deg, 30 deg, 28 deg)
        decision = None
        yaws = [26.0, 31.0, 28.0, 32.0, 27.0, 33.0, 29.0]
        for i in range(35):  # 3.5s > LOOKING_AWAY_SECS 3.0s
            t = 100.0 + i * 0.1
            yaw_val = yaws[i % len(yaws)]
            f = self._make_features(t, head_yaw=yaw_val, head_direction=HeadDirection.TURNED_RIGHT)
            decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.POSSIBLE_DISTRACTION)

    # ──────────────────────────────────────────────────────────────────
    # 14. An eligible alert arrives while another audio clip is playing
    # ──────────────────────────────────────────────────────────────────
    def test_14_eligible_alert_arrives_while_another_audio_playing(self):
        audio = CentralAudioManager(enabled=True)
        # Play priority 5 distraction alert
        audio.update_state(StudyState.DISTRACTED, cooldown=0.0)
        self.assertEqual(audio.active_state, StudyState.DISTRACTED)
        self.assertEqual(audio._active_priority, 5)

        # Higher priority alert arrives: StudyState.FACE_OCCLUDED (Priority 3)
        preempted = audio.update_state(StudyState.FACE_OCCLUDED, cooldown=0.0)
        self.assertTrue(preempted)
        self.assertEqual(audio.active_state, StudyState.FACE_OCCLUDED)
        self.assertEqual(audio._active_priority, 3)
        audio.stop()

    # ──────────────────────────────────────────────────────────────────
    # 15. The student resumes studying and the warning stops
    # ──────────────────────────────────────────────────────────────────
    def test_15_student_resumes_studying_warning_stops(self):
        audio = CentralAudioManager(enabled=True)
        # Trigger alert
        audio.update_state(StudyState.DISTRACTED, cooldown=0.0)
        self.assertTrue(audio.is_playing)

        # Clean studying resumes
        audio.update_state(StudyState.STUDYING)
        self.assertFalse(audio.is_playing)
        self.assertIsNone(audio.active_state)

    # ──────────────────────────────────────────────────────────────────
    # 16. The UI receives latest state rather than stale state
    # ──────────────────────────────────────────────────────────────────
    def test_16_ui_receives_latest_state_rather_than_stale(self):
        # Trigger phone distraction
        for i in range(35):
            t = 100.0 + i * 0.1
            self.engine.update(self._make_features(t, phone_detected=True))
        self.assertEqual(self.engine.primary_state, BehaviorLabel.POSSIBLE_DISTRACTION)

        # Immediate return to clean study
        t_clean = 104.0
        decision_clean = self.engine.update(self._make_features(t_clean, phone_detected=False))
        # UI immediately receives RECOVERING with fresh timestamp, NOT stale DISTRACTED
        self.assertEqual(decision_clean.primary_state, BehaviorLabel.RECOVERING)
        self.assertEqual(decision_clean.features.timestamp, t_clean)
        self.assertIn("recover", decision_clean.trigger_condition.lower())

    # ──────────────────────────────────────────────────────────────────
    # Section 3 A, B, C Specific Edge Cases
    # ──────────────────────────────────────────────────────────────────
    def test_17_looking_around_room_repeatedly(self):
        # Repeated head turns over room
        pose = ObservablePoseFeatures(repeated_head_turns=True)
        decision = None
        for i in range(35):  # 3.5s
            t = 100.0 + i * 0.1
            f = self._make_features(t, pose_features=pose)
            decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.POSSIBLE_DISTRACTION)
        self.assertIn("room", decision.trigger_condition.lower())

    def test_18_head_down_on_desk_fatigue(self):
        # Face lost, leaning forward with minimal upper body movement (head on desk)
        decision = None
        for i in range(35):  # 3.5s > 2.8s
            t = 100.0 + i * 0.1
            f = self._make_features(
                t,
                face_detected=False,
                shoulder_posture=ShoulderPosture.LEANING_FORWARD,
                upper_body_motion=0.002,
                book_detected=False,
            )
            decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.POSSIBLE_DROWSINESS)
        self.assertIn("head down on desk", decision.trigger_condition.lower())

    def test_19_leaning_back_inactive(self):
        # Leaning back inactive with motionless posture
        pose = ObservablePoseFeatures(minimal_upper_body_movement=True)
        decision = None
        for i in range(70):  # 7.0s > 6.0s
            t = 100.0 + i * 0.1
            f = self._make_features(
                t,
                shoulder_posture=ShoulderPosture.LEANING_BACKWARD,
                upper_body_motion=0.001,
                book_detected=False,
                laptop_detected=False,
                pose_features=pose,
            )
            decision = self.engine.update(f)
        self.assertEqual(decision.primary_state, BehaviorLabel.POSSIBLE_DISTRACTION)
        self.assertIn("inactivity", decision.trigger_condition.lower())


if __name__ == "__main__":
    unittest.main()

