"""
tests/test_web_app.py — Automated Test Suite for Web Dashboard Mode.
Verifies FastAPI endpoints, WebSocket lifecycle, SessionPipeline isolation,
RecommendationEngine, Audio routing, Flow control, and Resource cleanup.
"""

from __future__ import annotations

import io
import time
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.services.recommendation.recommendation_engine import RecommendationEngine
from backend.app.schemas.events import AlertData, ObservationData, RecommendationData, StateUpdateEvent
from backend.app.pipelines.session_pipeline import SessionPipeline
from backend.app.services.decision.state_machine import StudyState


class TestWebAppMode(unittest.TestCase):
    """Test suite for FastAPI backend, SessionPipeline, Recommendations, and WebSocket."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # ──────────────────────────────────────────────────────────────────
    # 1. REST Endpoints & Health Check
    # ──────────────────────────────────────────────────────────────────
    def test_01_backend_health_check(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("device", data)
        self.assertIn("yolo_loaded", data)
        self.assertIn("uptime_seconds", data)

    def test_02_system_config_endpoint(self):
        resp = self.client.get("/api/config")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("distraction_threshold_sec", data)
        self.assertIn("inactivity_threshold_sec", data)
        self.assertIn("occlusion_threshold_sec", data)
        self.assertIn("drowsiness_threshold_sec", data)

    def test_03_static_frontend_and_assets(self):
        # Index HTML
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("<title>AI Study Focus Monitor", resp.text)

        # CSS
        resp_css = self.client.get("/css/dashboard.css")
        self.assertEqual(resp_css.status_code, 200)

        # JS
        resp_js = self.client.get("/js/app.js")
        self.assertEqual(resp_js.status_code, 200)

        # Audio asset
        resp_audio = self.client.get("/assets/audio/occlusion_alert.mp3")
        self.assertEqual(resp_audio.status_code, 200)

    # ──────────────────────────────────────────────────────────────────
    # 2. Recommendation Engine
    # ──────────────────────────────────────────────────────────────────
    def test_04_recommendations_mapping(self):
        # Inactive
        rec = RecommendationEngine.get_recommendation(StudyState.STUDYING, is_active=False)
        self.assertEqual(rec.title, "Session Inactive")
        self.assertEqual(rec.severity, "info")

        # Camera error
        rec = RecommendationEngine.get_recommendation(StudyState.CAMERA_ERROR, diagnostic_reason="No frames")
        self.assertEqual(rec.title, "Camera Unavailable")
        self.assertEqual(rec.severity, "critical")
        self.assertIn("No frames", rec.reason)

        # Low visibility
        rec = RecommendationEngine.get_recommendation(StudyState.LOW_VISIBILITY)
        self.assertEqual(rec.title, "Low Lighting Detected")
        self.assertEqual(rec.severity, "warning")

        # Face occluded
        rec = RecommendationEngine.get_recommendation(StudyState.FACE_OCCLUDED, duration_seconds=3.5)
        self.assertEqual(rec.title, "Face or Workspace Blocked")
        self.assertEqual(rec.severity, "warning")

        # Inactivity
        rec = RecommendationEngine.get_recommendation(StudyState.INACTIVITY_WARNING, duration_seconds=12.0)
        self.assertEqual(rec.title, "Sustained Inactivity")
        self.assertEqual(rec.severity, "warning")

        # Distraction with phone
        rec = RecommendationEngine.get_recommendation(
            StudyState.DISTRACTED,
            diagnostic_reason="Phone in hand",
            observations={"phone_detected": True},
        )
        self.assertIn("Phone", rec.title)
        self.assertEqual(rec.severity, "warning")

        # Drowsiness
        rec = RecommendationEngine.get_recommendation(StudyState.POSSIBLE_DROWSINESS, duration_seconds=2.0)
        self.assertEqual(rec.title, "Signs of Fatigue")
        self.assertEqual(rec.severity, "warning")

        # Studying
        rec = RecommendationEngine.get_recommendation(StudyState.STUDYING)
        self.assertEqual(rec.title, "Great Study Flow!")
        self.assertEqual(rec.severity, "positive")

    # ──────────────────────────────────────────────────────────────────
    # 3. Session Pipeline Frame Processing & Flow Control
    # ──────────────────────────────────────────────────────────────────
    def _create_synthetic_jpeg(self, width: int = 320, height: int = 240) -> bytes:
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:] = (120, 100, 90)
        _, encoded = cv2.imencode(".jpg", img)
        return encoded.tobytes()

    def test_05_session_pipeline_valid_frame(self):
        pipeline = SessionPipeline()
        frame_bytes = self._create_synthetic_jpeg()

        event = pipeline.process_frame_bytes(frame_bytes, timestamp=100.0)
        self.assertIsInstance(event, StateUpdateEvent)
        self.assertEqual(event.session_id, pipeline.session_id)
        self.assertEqual(event.frame_id, 1)
        self.assertIsNotNone(event.state)
        self.assertIsNotNone(event.observations)
        self.assertIsNotNone(event.recommendation)
        pipeline.close()

    def test_06_session_pipeline_corrupted_frame_handling(self):
        pipeline = SessionPipeline()
        corrupt_bytes = b"NOT_A_VALID_JPEG_IMAGE_DATA_12345"

        event = pipeline.process_frame_bytes(corrupt_bytes, timestamp=100.0)
        self.assertEqual(event.state, "CAMERA_ERROR")
        self.assertEqual(event.observations.camera_health, "FAULT")
        self.assertEqual(event.recommendation.severity, "critical")
        pipeline.close()

    def test_07_oversized_payload_rejection(self):
        pipeline = SessionPipeline()
        oversized_bytes = b"0" * (3 * 1024 * 1024)  # 3 MB > 2.5 MB limit

        event = pipeline.process_frame_bytes(oversized_bytes, timestamp=100.0)
        self.assertEqual(event.state, "CAMERA_ERROR")
        self.assertIn("exceeded", event.diagnostic_reason.lower())
        pipeline.close()

    # ──────────────────────────────────────────────────────────────────
    # 4. Session Isolation & Resource Cleanup
    # ──────────────────────────────────────────────────────────────────
    def test_08_session_isolation(self):
        session1 = SessionPipeline()
        session2 = SessionPipeline()

        self.assertNotEqual(session1.session_id, session2.session_id)
        self.assertIsNot(session1.focus_monitor, session2.focus_monitor)
        self.assertIsNot(session1.focus_monitor.decision_engine, session2.focus_monitor.decision_engine)

        # Feed frame to session 1 only
        frame_bytes = self._create_synthetic_jpeg()
        session1.process_frame_bytes(frame_bytes, timestamp=100.0)

        self.assertEqual(session1.frame_count, 1)
        self.assertEqual(session2.frame_count, 0)

        session1.close()
        session2.close()

    def test_09_session_cleanup(self):
        session = SessionPipeline()
        self.assertTrue(session.active)
        session.close()
        self.assertFalse(session.active)

    # ──────────────────────────────────────────────────────────────────
    # 5. Audio Alert Priority & Preemption in Web Mode
    # ──────────────────────────────────────────────────────────────────
    def test_10_alert_priority_and_preemption(self):
        session = SessionPipeline()

        # Trigger P5 distraction alert
        alert_p5 = session._evaluate_alert(100.0, StudyState.DISTRACTED, None)
        self.assertTrue(alert_p5.active)
        self.assertEqual(alert_p5.priority, 5)
        self.assertIn("distraction", alert_p5.audio_file)

        # Higher priority P3 occlusion alert preempts P5
        alert_p3 = session._evaluate_alert(101.0, StudyState.FACE_OCCLUDED, None)
        self.assertTrue(alert_p3.active)
        self.assertEqual(alert_p3.priority, 3)
        self.assertIn("occlusion", alert_p3.audio_file)

        # Recovery clears alert
        alert_clean = session._evaluate_alert(102.0, StudyState.RECOVERING, None)
        self.assertFalse(alert_clean.active)

        session.close()

    # ──────────────────────────────────────────────────────────────────
    # 6. WebSocket Streaming & Flow Control
    # ──────────────────────────────────────────────────────────────────
    def test_11_websocket_connection_and_streaming(self):
        with self.client.websocket_connect("/ws/monitor") as websocket:
            # First message received is initial connection event
            init_data = websocket.receive_json()
            self.assertIn("state", init_data)
            self.assertIn("session_id", init_data)

            # Send a frame blob
            frame_bytes = self._create_synthetic_jpeg()
            websocket.send_bytes(frame_bytes)

            # Server immediately replies with processed event (Flow Control ACK)
            event_data = websocket.receive_json()
            self.assertIn("state", event_data)
            self.assertEqual(event_data["frame_id"], 1)

            # Test text control ping
            websocket.send_text("ping")
            pong = websocket.receive_json()
            self.assertEqual(pong.get("type"), "pong")

            # Test text control reset
            websocket.send_text("reset")
            res = websocket.receive_json()
            self.assertEqual(res.get("type"), "info")

            websocket.close()

    def test_12_reset_session_rest_endpoint(self):
        resp = self.client.post("/api/session/reset", json={"action": "reset", "session_id": "nonexistent"})
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()

