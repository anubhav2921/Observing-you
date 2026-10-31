"""
tests/test_study_monitor.py — Automated Unit Tests for AI Study Focus Monitor.
Tests all 20 specified scenarios for the State Machine and Central Audio Controller
using mocked detections with no physical webcam or audio hardware required.
"""

import os
import sys
import time
import unittest

# Ensure parent directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import backend.app.core.config as config
from backend.app.services.audio.audio_alerts import CentralAudioManager
from backend.app.services.decision.state_machine import DetectorSignals, StudyState, StudyStateMachine


class TestStudyMonitorScenarios(unittest.TestCase):
    """20 scenario test suite for the state machine and audio controller."""

    def setUp(self):
        self.sm = StudyStateMachine(logger=None)
        # Fast configuration thresholds for deterministic testing
        config.STUDENT_ABSENT_SECS = 4.0
        config.FACE_OCCLUDED_SECS = 3.0
        config.LOOKING_AWAY_SECS = 3.0
        config.PHONE_DETECT_SECS = 3.0
        config.DROWSINESS_SUSTAINED_SECS = 1.8
        config.CAMERA_STARING_UNCONFIRMED_SECS = 3.0
        config.INACTIVITY_WARNING_SECS = 6.0
        config.RECOVERY_STABILITY_SECS = 1.0
        config.ALERT_COOLDOWN_SECONDS = 5.0

    def _step(self, t: float, **kwargs) -> StudyState:
        """Helper to create and feed a DetectorSignals instance at monotonic time t."""
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
            "head_pitch": 5.0,
            "phone_detected": False,
            "book_detected": False,
            "laptop_detected": False,
            "hands_near_face": False,
            "motion_score": 0.012,
        }
        defaults.update(kwargs)
        signals = DetectorSignals(**defaults)
        eval_res = self.sm.update(signals)
        return eval_res.state

    # ──────────────────────────────────────────────────────────────────
    # Scenario 1: Student reads with face fully visible
    # ──────────────────────────────────────────────────────────────────
    def test_01_student_reads_face_fully_visible(self):
        # Head pitch downward in reading zone (e.g. 18 deg) with book detected
        state = None
        for i in range(20):
            t = 100.0 + i * 0.1
            state = self._step(t, head_pitch=18.0, head_yaw=2.0, book_detected=True)
        self.assertEqual(state, StudyState.STUDYING_READING)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 2: Student reads with face partly hidden by a book
    # ──────────────────────────────────────────────────────────────────
    def test_02_student_reads_face_partly_hidden_by_book(self):
        # Face detected with lower landmarks occluded by book
        state = None
        for i in range(25):
            t = 100.0 + i * 0.1
            state = self._step(t, head_pitch=22.0, book_detected=True, hands_near_face=False)
        self.assertEqual(state, StudyState.STUDYING_READING)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 3: Book fully hides the face for several seconds
    # ──────────────────────────────────────────────────────────────────
    def test_03_book_fully_hides_face_while_reading(self):
        # Face landmarks drop out, but book is detected and pitch was downward
        state = None
        for i in range(40):  # 4 seconds
            t = 100.0 + i * 0.1
            state = self._step(t, face_detected=False, book_detected=True, head_pitch=20.0, motion_score=0.005)
        # Should remain reading, NOT falsely flagged as deliberate occlusion
        self.assertEqual(state, StudyState.STUDYING_READING)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 4: Student covers their face with a hand
    # ──────────────────────────────────────────────────────────────────
    def test_04_student_covers_face_with_hand(self):
        # Face not detected, hands over face, NO book
        state = None
        for i in range(35):  # 3.5 seconds (> FACE_OCCLUDED_SECS 3.0s)
            t = 100.0 + i * 0.1
            state = self._step(t, face_detected=False, hands_near_face=True, book_detected=False)
        self.assertEqual(state, StudyState.FACE_OCCLUDED)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 5: Student leaves the chair (absence)
    # ──────────────────────────────────────────────────────────────────
    def test_05_student_leaves_chair(self):
        # Person not detected by YOLO
        state = None
        for i in range(45):  # 4.5 seconds (> STUDENT_ABSENT_SECS 4.0s)
            t = 100.0 + i * 0.1
            state = self._step(t, person_detected=False, face_detected=False)
        self.assertEqual(state, StudyState.STUDENT_ABSENT)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 6: Student looks down at a notebook
    # ──────────────────────────────────────────────────────────────────
    def test_06_student_looks_down_at_notebook(self):
        state = None
        for i in range(25):
            t = 100.0 + i * 0.1
            # Pitch down 20 deg, yaw centered, normal studying/reading
            state = self._step(t, head_pitch=20.0, head_yaw=0.0, ear=0.28)
        self.assertEqual(state, StudyState.STUDYING_READING)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 7: Student stares at the camera without observable study activity
    # ──────────────────────────────────────────────────────────────────
    def test_07_student_stares_at_camera_inactivity(self):
        # Phase 1: 3.5 seconds staring -> STUDY_ACTIVITY_UNCONFIRMED
        state = None
        for i in range(36):  # 3.6 seconds
            t = 100.0 + i * 0.1
            state = self._step(t, head_pitch=0.0, head_yaw=0.0, book_detected=False, motion_score=0.001)
        self.assertEqual(state, StudyState.STUDY_ACTIVITY_UNCONFIRMED)

        # Phase 2: Staring continues past 6.0 seconds -> INACTIVITY_WARNING
        for i in range(36, 65):  # up to 6.5s
            t = 100.0 + i * 0.1
            state = self._step(t, head_pitch=0.0, head_yaw=0.0, book_detected=False, motion_score=0.001)
        self.assertEqual(state, StudyState.INACTIVITY_WARNING)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 8: Student briefly looks away (under threshold)
    # ──────────────────────────────────────────────────────────────────
    def test_08_student_briefly_looks_away(self):
        # Initial studying
        self._step(100.0, head_yaw=0.0)
        # Briefly look away for 1.2s (< LOOKING_AWAY_SECS 3.0s)
        state = None
        for i in range(12):
            t = 101.0 + i * 0.1
            state = self._step(t, head_yaw=35.0)
        # Must NOT trigger LOOKING_AWAY yet
        self.assertNotEqual(state, StudyState.LOOKING_AWAY)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 9: Student uses a phone while off-task
    # ──────────────────────────────────────────────────────────────────
    def test_09_student_uses_phone_off_task(self):
        state = None
        for i in range(35):  # 3.5s (> PHONE_DETECT_SECS 3.0s)
            t = 100.0 + i * 0.1
            state = self._step(t, phone_detected=True)
        self.assertEqual(state, StudyState.DISTRACTED)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 10: Student blinks normally (no false sleep alarm)
    # ──────────────────────────────────────────────────────────────────
    def test_10_normal_blinking_no_sleep_alarm(self):
        t = 100.0
        # Blink 1: 0.2s eyes closed
        for _ in range(2):
            t += 0.1
            state = self._step(t, ear=0.15)
            self.assertNotEqual(state, StudyState.POSSIBLE_DROWSINESS)
        # Eyes open 0.5s
        for _ in range(5):
            t += 0.1
            state = self._step(t, ear=0.32)
            self.assertNotEqual(state, StudyState.POSSIBLE_DROWSINESS)
        # Blink 2: 0.2s eyes closed
        for _ in range(2):
            t += 0.1
            state = self._step(t, ear=0.14)
            self.assertNotEqual(state, StudyState.POSSIBLE_DROWSINESS)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 11: Sustained drowsiness-like cues
    # ──────────────────────────────────────────────────────────────────
    def test_11_sustained_drowsiness_cues(self):
        state = None
        for i in range(22):  # 2.2s (> DROWSINESS_SUSTAINED_SECS 1.8s)
            t = 100.0 + i * 0.1
            state = self._step(t, ear=0.12)
        self.assertEqual(state, StudyState.POSSIBLE_DROWSINESS)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 12: Camera is disconnected
    # ──────────────────────────────────────────────────────────────────
    def test_12_camera_disconnected(self):
        state = self._step(100.0, camera_valid=False)
        self.assertEqual(state, StudyState.CAMERA_ERROR)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 13: Camera returns after disconnection
    # ──────────────────────────────────────────────────────────────────
    def test_13_camera_returns_after_disconnection(self):
        # Camera error
        self._step(100.0, camera_valid=False)
        self.assertEqual(self.sm.current_state, StudyState.CAMERA_ERROR)
        # Camera returns, user is studying
        state = None
        for i in range(15):  # 1.5s (> RECOVERY_STABILITY_SECS 1.0s)
            t = 101.0 + i * 0.1
            state = self._step(t, camera_valid=True, person_detected=True, face_detected=True)
        self.assertIn(state, (StudyState.STUDYING, StudyState.STUDYING_READING))

    # ──────────────────────────────────────────────────────────────────
    # Scenario 14: Frames become dark, invalid, or frozen
    # ──────────────────────────────────────────────────────────────────
    def test_14_frames_dark_or_frozen(self):
        # Low visibility (dark)
        state_dark = self._step(100.0, low_visibility=True)
        self.assertEqual(state_dark, StudyState.LOW_VISIBILITY)

        # Frozen frame
        state_frozen = self._step(101.0, frame_frozen=True)
        self.assertEqual(state_frozen, StudyState.CAMERA_ERROR)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 15: Warning is playing when student resumes studying
    # ──────────────────────────────────────────────────────────────────
    def test_15_warning_playing_stops_when_student_resumes(self):
        audio = CentralAudioManager(enabled=False)
        audio._mixer_ready = True
        audio._is_playing = True
        audio._active_state = StudyState.DISTRACTED
        audio._active_priority = 5

        # Student resumes studying
        triggered = audio.update_state(StudyState.STUDYING)
        self.assertFalse(triggered)
        self.assertFalse(audio.is_playing)
        self.assertIsNone(audio.active_state)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 16: Two alerts become eligible simultaneously
    # ──────────────────────────────────────────────────────────────────
    def test_16_simultaneous_alerts_respect_priority(self):
        # Camera error (Priority 1) should override Distraction (Priority 5)
        p_cam = CentralAudioManager.STATE_PRIORITY[StudyState.CAMERA_ERROR]
        p_dist = CentralAudioManager.STATE_PRIORITY[StudyState.DISTRACTED]
        self.assertLess(p_cam, p_dist)

        p_absent = CentralAudioManager.STATE_PRIORITY[StudyState.STUDENT_ABSENT]
        p_sleep = CentralAudioManager.STATE_PRIORITY[StudyState.POSSIBLE_DROWSINESS]
        self.assertLess(p_absent, p_sleep)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 17: An audio file is missing
    # ──────────────────────────────────────────────────────────────────
    def test_17_audio_file_missing_graceful_handling(self):
        config.AUDIO_DISTRACTION_FILE = "non_existent_file_xyz_123.mp3"
        audio = CentralAudioManager(enabled=False)
        # Should not raise exception
        self.assertIsNotNone(audio)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 18: Detector predictions fluctuate between states
    # ──────────────────────────────────────────────────────────────────
    def test_18_fluctuating_predictions_hysteresis_smoothing(self):
        # Rapidly flip between phone and studying on alternating 50ms frames
        state = None
        for i in range(10):
            t = 100.0 + i * 0.05
            phone = (i % 2 == 0)
            state = self._step(t, phone_detected=phone)
        # Hysteresis prevents rapid flipping to DISTRACTED without sustained duration
        self.assertNotEqual(state, StudyState.DISTRACTED)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 19: Face is hidden while student is visibly reading
    # ──────────────────────────────────────────────────────────────────
    def test_19_face_hidden_while_visibly_reading(self):
        # Person present, face not detected, but book present and motion detected
        state = None
        for i in range(35):  # 3.5s
            t = 100.0 + i * 0.1
            state = self._step(t, face_detected=False, book_detected=True, motion_score=0.008)
        self.assertEqual(state, StudyState.STUDYING_READING)
        self.assertNotEqual(state, StudyState.FACE_OCCLUDED)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 20: Student resumes normal activity after a warning
    # ──────────────────────────────────────────────────────────────────
    def test_20_student_resumes_normal_activity_after_warning(self):
        # Trigger DISTRACTED first (phone for 3.5s)
        for i in range(35):
            t = 100.0 + i * 0.1
            self._step(t, phone_detected=True)
        self.assertEqual(self.sm.current_state, StudyState.DISTRACTED)

        # Phone removed, student resumes studying
        # First 0.5s: RECOVERING
        state = self._step(104.0, phone_detected=False, head_yaw=0.0, ear=0.30)
        self.assertEqual(state, StudyState.RECOVERING)

        # After recovery stability (1.2s later): STUDYING
        for i in range(12):
            t = 104.1 + i * 0.1
            state = self._step(t, phone_detected=False, head_yaw=0.0, ear=0.30)
        self.assertEqual(state, StudyState.STUDYING)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 21: Face intensely covered or hidden ("face nahi dikh raha")
    # ──────────────────────────────────────────────────────────────────
    def test_21_face_intensely_covered_or_hidden_triggers_occlusion(self):
        # Person present, face missing / covered (hands not detected, cloth/blanket/arms)
        state = None
        for i in range(35):  # 3.5s (> FACE_OCCLUDED_SECS 3.0s)
            t = 100.0 + i * 0.1
            state = self._step(
                t,
                person_detected=True,
                face_detected=False,
                hands_near_face=False,
                book_detected=False,
            )
        self.assertEqual(state, StudyState.FACE_OCCLUDED)

    # ──────────────────────────────────────────────────────────────────
    # Scenario 22: Occlusion audio file resolution and playback
    # ──────────────────────────────────────────────────────────────────
    def test_22_occlusion_audio_configuration(self):
        # Verify custom occlusion audio config is resolved
        self.assertTrue(bool(config.AUDIO_OCCLUSION_FILE))
        self.assertTrue("InShot" in config.AUDIO_OCCLUSION_FILE)
        audio = CentralAudioManager(enabled=True)
        self.assertIn("occlusion", audio._sounds)
        self.assertIsNotNone(audio._sounds["occlusion"])


if __name__ == "__main__":
    unittest.main()
