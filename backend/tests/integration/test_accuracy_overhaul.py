"""
tests/integration/test_accuracy_overhaul.py — Comprehensive Accuracy & Behavior Validation Suite.
Implements the 10 core audit tests (TEST A through TEST J) + Diagnostic Mode validation.
Purely mocked and deterministic — executes in under 2 seconds.
"""

from __future__ import annotations

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import backend.app.core.config as config
from backend.app.services.behavior.behavior_types import (
    BehaviorLabel,
    EyeState,
    HandActivity,
    HeadDirection,
    ObservablePoseFeatures,
    ShoulderPosture,
    UpperBodyFeatures,
)
from backend.app.services.decision.temporal_decision_engine import TemporalDecisionEngine
from backend.app.services.audio.audio_alerts import CentralAudioManager


class TestAccuracyOverhaulSuite(unittest.TestCase):
    """
    Accuracy overhaul test harness validating temporal evidence,
    non-disruptive study switching, blink rejection, and audio gating.
    """

    def setUp(self):
        config.DROWSINESS_SUSTAINED_SECS = 2.0
        config.BRIEF_BLINK_MAX_SECS = 0.5
        config.LOOKING_AWAY_SECS = 4.0
        config.PHONE_DETECT_SECS = 3.0
        config.RECOVERY_STABILITY_SECS = 1.0
        config.RECOVERY_DROWSINESS_SECS = 1.5
        config.DIAGNOSTIC_MODE = False
        config.ALERT_COOLDOWN_SECONDS = 5.0
        self.engine = TemporalDecisionEngine()
        self.audio = CentralAudioManager(enabled=True)

    def tearDown(self):
        self.audio.stop()
        config.DIAGNOSTIC_MODE = False

    def test_A_eyes_open_with_normal_head_movement(self):
        """TEST A: Eyes open with normal head movement (yaw +-12 deg, pitch +-8 deg) -> No drowsiness alert."""
        t = 100.0
        for i in range(25):
            t += 0.1
            yaw = 10.0 if (i % 2 == 0) else -10.0
            pitch = 6.0 if (i % 3 == 0) else -4.0
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=True,
                landmark_validity=True,
                head_yaw=yaw,
                head_pitch=pitch,
                ear=0.29,
                eye_state=EyeState.EYES_OPEN,
                shoulders_detected=True,
                shoulder_posture=ShoulderPosture.UPRIGHT,
                head_direction=HeadDirection.FACING_SCREEN,
            )
            dec = self.engine.update(f)
            self.assertNotEqual(dec.primary_state, BehaviorLabel.POSSIBLE_DROWSINESS)
            self.assertFalse(dec.alert_eligible)
            self.assertFalse(self.audio.update_state(dec.primary_state))

    def test_B_natural_blinking(self):
        """TEST B: Natural brief blinking (< 0.4s) -> No drowsiness alert."""
        t = 200.0
        # 1.0s open eyes
        for _ in range(10):
            t += 0.1
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=True,
                landmark_validity=True,
                ear=0.28,
                eye_state=EyeState.EYES_OPEN,
                head_direction=HeadDirection.FACING_SCREEN,
            )
            self.engine.update(f)

        # 0.3s blink (3 frames closed with brief_eye_closure and normal_blinking flags)
        for _ in range(3):
            t += 0.1
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=True,
                landmark_validity=True,
                ear=0.14,
                eye_state=EyeState.EYES_CLOSED,
                pose_features=ObservablePoseFeatures(brief_eye_closure=True, normal_blinking=True),
                head_direction=HeadDirection.FACING_SCREEN,
            )
            dec = self.engine.update(f)
            self.assertNotEqual(dec.primary_state, BehaviorLabel.POSSIBLE_DROWSINESS)
            self.assertFalse(dec.alert_eligible)

        # Reopen
        t += 0.1
        f = UpperBodyFeatures(
            timestamp=t,
            person_detected=True,
            face_detected=True,
            landmark_validity=True,
            ear=0.28,
            eye_state=EyeState.EYES_OPEN,
            head_direction=HeadDirection.FACING_SCREEN,
        )
        dec = self.engine.update(f)
        self.assertIn(dec.primary_state, (BehaviorLabel.STUDYING_SCREEN, BehaviorLabel.STUDYING_READING_WRITING))

    def test_C_reading_physical_book(self):
        """TEST C: Reading a physical book (downward pitch, book detected) -> STUDYING_READING_WRITING."""
        t = 300.0
        for _ in range(15):
            t += 0.1
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=True,
                landmark_validity=True,
                head_pitch=22.0,
                head_direction=HeadDirection.TILTED_DOWN,
                book_detected=True,
                ear=0.21,  # Natural foreshortening when looking down
                eye_state=EyeState.EYES_OPEN,
            )
            dec = self.engine.update(f)
            self.assertEqual(dec.primary_state, BehaviorLabel.STUDYING_READING_WRITING)
            self.assertFalse(dec.alert_eligible)

    def test_D_switching_screen_and_notebook(self):
        """TEST D: Switching between screen and notebook remains uninterrupted productive studying."""
        t = 400.0
        # 2 seconds studying on screen
        for _ in range(20):
            t += 0.1
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=True,
                landmark_validity=True,
                head_direction=HeadDirection.FACING_SCREEN,
                eye_state=EyeState.EYES_OPEN,
                ear=0.28,
            )
            dec = self.engine.update(f)
            self.assertEqual(dec.primary_state, BehaviorLabel.STUDYING_SCREEN)

        enter_time_before = self.engine.state_enter_time

        # Switch to reading notes on desk
        for _ in range(20):
            t += 0.1
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=True,
                landmark_validity=True,
                head_pitch=20.0,
                head_direction=HeadDirection.TILTED_DOWN,
                book_detected=True,
                ear=0.22,
                eye_state=EyeState.EYES_OPEN,
            )
            dec = self.engine.update(f)

        # After rolling consensus window (0.5s = 5 frames), primary adopts STUDYING_READING_WRITING
        self.assertEqual(dec.primary_state, BehaviorLabel.STUDYING_READING_WRITING)
        # Duration should accumulate across study modes, not wipe
        self.assertEqual(self.engine.state_enter_time, enter_time_before)
        self.assertFalse(dec.alert_eligible)

    def test_E_normal_posture_adjustment(self):
        """TEST E: Posture adjustment (slight shoulder tilt or lean) does not trigger false alerts."""
        t = 500.0
        for _ in range(15):
            t += 0.1
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=True,
                landmark_validity=True,
                head_direction=HeadDirection.FACING_SCREEN,
                eye_state=EyeState.EYES_OPEN,
                ear=0.27,
                shoulders_detected=True,
                shoulder_posture=ShoulderPosture.LEANING_FORWARD,
                shoulder_tilt_deg=8.0,
            )
            dec = self.engine.update(f)
            self.assertIn(dec.primary_state, (BehaviorLabel.STUDYING_SCREEN, BehaviorLabel.STUDYING_READING_WRITING))
            self.assertFalse(dec.alert_eligible)

    def test_F_face_temporarily_partially_obscured(self):
        """TEST F: Hand near chin (thinking) does not produce false eye-closure or drowsiness alert."""
        t = 600.0
        for _ in range(15):
            t += 0.1
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=True,
                landmark_validity=True,
                hand_near_chin=True,
                hand_to_face_iou=0.18,
                ear=0.26,
                eye_state=EyeState.EYES_OPEN,
                head_direction=HeadDirection.FACING_SCREEN,
            )
            dec = self.engine.update(f)
            self.assertNotEqual(dec.primary_state, BehaviorLabel.POSSIBLE_DROWSINESS)
            self.assertNotEqual(dec.primary_state, BehaviorLabel.FACE_FULLY_OCCLUDED)

    def test_G_phone_detection_requires_temporal_confirmation(self):
        """TEST G: Momentary phone detection flicker (< 3.0s) does not immediately trigger alert."""
        t = 700.0
        # Frame with phone flicker for 1.0s
        for _ in range(10):
            t += 0.1
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=True,
                landmark_validity=True,
                phone_detected=True,
                head_direction=HeadDirection.FACING_SCREEN,
                eye_state=EyeState.EYES_OPEN,
            )
            dec = self.engine.update(f)
            # Not yet reached threshold of 3.0s
            self.assertNotEqual(dec.primary_state, BehaviorLabel.POSSIBLE_DISTRACTION)

        # Phone removed: timer resets
        for _ in range(5):
            t += 0.1
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=True,
                landmark_validity=True,
                phone_detected=False,
                head_direction=HeadDirection.FACING_SCREEN,
                eye_state=EyeState.EYES_OPEN,
            )
            dec = self.engine.update(f)
            self.assertNotEqual(dec.primary_state, BehaviorLabel.POSSIBLE_DISTRACTION)

    def test_H_sustained_verified_fatigue_indicators(self):
        """TEST H: Sustained verified eye closure (> 2.0s) triggers POSSIBLE_DROWSINESS."""
        t = 800.0
        dec = None
        # Sustained closure for 2.2s (22 frames)
        for _ in range(23):
            t += 0.1
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=True,
                landmark_validity=True,
                ear=0.12,
                eye_state=EyeState.EYES_CLOSED,
                pose_features=ObservablePoseFeatures(sustained_eye_closure=True),
                head_direction=HeadDirection.FACING_SCREEN,
            )
            dec = self.engine.update(f)

        self.assertEqual(dec.primary_state, BehaviorLabel.POSSIBLE_DROWSINESS)
        self.assertTrue(dec.alert_eligible)

    def test_I_no_face_visible_handled_as_occlusion_not_drowsiness(self):
        """TEST I: Face covered or absent from frame is NEVER classified as drowsiness."""
        t = 900.0
        for _ in range(35):
            t += 0.1
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=False,
                landmark_validity=False,
                ear=None,
                eye_state=EyeState.UNKNOWN,
                hand_to_face_iou=0.45,
                pose_features=ObservablePoseFeatures(face_covered_by_hand=True),
            )
            dec = self.engine.update(f)
            self.assertNotEqual(dec.primary_state, BehaviorLabel.POSSIBLE_DROWSINESS)

    def test_J_repeated_contradictory_detections_stabilization(self):
        """TEST J: Rapid alternating noisy predictions are smoothed and do not cause rapid alert oscillations."""
        t = 1000.0
        states = []
        for i in range(20):
            t += 0.05
            # Alternating signals
            facing = (i % 2 == 0)
            f = UpperBodyFeatures(
                timestamp=t,
                person_detected=True,
                face_detected=True,
                landmark_validity=True,
                head_yaw=0.0 if facing else 20.0,
                head_direction=HeadDirection.FACING_SCREEN if facing else HeadDirection.TURNED_RIGHT,
                ear=0.28,
                eye_state=EyeState.EYES_OPEN,
            )
            dec = self.engine.update(f)
            states.append(dec.primary_state)

        # Oscillating inputs should not rapid-fire alerts
        self.assertTrue(all(s not in (BehaviorLabel.POSSIBLE_DROWSINESS, BehaviorLabel.STUDENT_ABSENT) for s in states))

    def test_K_diagnostic_mode_suppresses_audio(self):
        """TEST K: Diagnostic mode strictly suppresses all audio playback even on alert states."""
        config.DIAGNOSTIC_MODE = True
        played = self.audio.update_state(BehaviorLabel.POSSIBLE_DROWSINESS)
        self.assertFalse(played)
        self.assertFalse(self.audio.is_playing)


if __name__ == "__main__":
    unittest.main()
