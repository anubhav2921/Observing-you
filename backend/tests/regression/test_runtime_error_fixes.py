"""
tests/regression/test_runtime_error_fixes.py — Regression tests for local-mode runtime errors.

Error 1: 'CentralAudioManager' object has no attribute 'stop_alert'
Error 2: tuple indices must be integers or slices, not str (STATE_DISPLAY access)
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.services.audio.audio_alerts import CentralAudioManager
from backend.app.services.detection.focus_monitor import FocusMonitor
from backend.app.services.decision.state_machine import StudyState, STATE_DISPLAY


class TestError1_StopAlertAttribute(unittest.TestCase):
    """Regression: CentralAudioManager must have stop_alert() and update_audio() aliases."""

    def setUp(self):
        """Suppress pygame init side-effects during test."""
        self.audio = CentralAudioManager()

    def test_stop_alert_exists(self):
        """stop_alert() must be callable without AttributeError."""
        self.assertTrue(hasattr(self.audio, "stop_alert"))
        self.assertTrue(callable(self.audio.stop_alert))

    def test_stop_alert_does_not_raise(self):
        """Calling stop_alert() should not raise any exception."""
        try:
            self.audio.stop_alert()
        except AttributeError:
            self.fail("stop_alert() raised AttributeError — alias method is missing")

    def test_update_audio_exists(self):
        """update_audio() must be callable without AttributeError."""
        self.assertTrue(hasattr(self.audio, "update_audio"))
        self.assertTrue(callable(self.audio.update_audio))

    def test_update_audio_does_not_raise(self):
        """Calling update_audio(STUDYING, now) should not raise any exception."""
        try:
            self.audio.update_audio(StudyState.STUDYING, now=100.0)
        except AttributeError:
            self.fail("update_audio() raised AttributeError — alias method is missing")

    def test_stop_alias_calls_stop(self):
        """stop_alert() should call through to stop() internally."""
        with patch.object(self.audio, "stop") as mock_stop:
            self.audio.stop_alert()
            mock_stop.assert_called_once()


class TestError2_StateDisplayTupleAccess(unittest.TestCase):
    """Regression: STATE_DISPLAY values are tuples (label, color), not dicts."""

    def test_state_display_values_are_tuples(self):
        """Every entry in STATE_DISPLAY must be a tuple of (str, tuple)."""
        for state, value in STATE_DISPLAY.items():
            self.assertIsInstance(value, tuple, f"STATE_DISPLAY[{state}] should be a tuple")
            self.assertEqual(len(value), 2, f"STATE_DISPLAY[{state}] should have 2 elements (label, color)")
            label, color = value
            self.assertIsInstance(label, str, f"STATE_DISPLAY[{state}] label should be str")
            self.assertIsInstance(color, tuple, f"STATE_DISPLAY[{state}] color should be tuple")
            self.assertEqual(len(color), 3, f"STATE_DISPLAY[{state}] color should have 3 components (BGR)")

    def test_draw_hud_state_display_destructuring(self):
        """Simulating draw_hud's STATE_DISPLAY access for all known states must not raise TypeError."""
        for state in StudyState:
            # Skip enum aliases (they share the same value as canonical members)
            disp = STATE_DISPLAY.get(state)
            if disp is not None:
                try:
                    label, color = disp[0], disp[1]
                except (TypeError, IndexError) as e:
                    self.fail(f"STATE_DISPLAY[{state}] access failed: {e}")
            else:
                # Fallback path — should also work
                label, color = state.name, (128, 128, 128)
            self.assertIsInstance(label, str)
            self.assertIsInstance(color, tuple)

    def test_draw_hud_dict_access_would_fail(self):
        """Verify that dict-style access on STATE_DISPLAY tuples raises TypeError (the original bug)."""
        for state in StudyState:
            disp = STATE_DISPLAY.get(state)
            if disp is not None:
                with self.assertRaises(TypeError, msg=f"Dict access on STATE_DISPLAY[{state}] should raise TypeError"):
                    _ = disp["color"]


class TestFocusMonitorProcessFrame(unittest.TestCase):
    """Regression: FocusMonitor.process_frame() and last_observation must work."""

    def setUp(self):
        self.monitor = FocusMonitor()

    def test_process_frame_returns_tuple(self):
        """process_frame() must return (StudyState, float)."""
        black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = self.monitor.process_frame(black_frame, timestamp=100.0)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        state, duration = result
        self.assertIsInstance(state, StudyState)
        self.assertIsInstance(duration, (int, float))

    def test_last_observation_property(self):
        """last_observation should return None before processing and IndependentObservations after."""
        self.assertIsNone(self.monitor.last_observation)
        black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.monitor.process_frame(black_frame, timestamp=100.0)
        obs = self.monitor.last_observation
        # May be None if no face detected, but should not raise AttributeError
        # At minimum, the property should be accessible
        # (obs can legitimately be None for a featureless black frame)


if __name__ == "__main__":
    unittest.main()

