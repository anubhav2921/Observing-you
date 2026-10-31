"""
backend/scripts/run_webcam.py — Standalone Local OpenCV Study Monitor (Mode A).
Runs real-time camera capture, YOLO detection, FocusMonitor, HUD visualization, and local audio alerts.
"""

from __future__ import annotations

import sys
import time
from typing import Any, Dict, Optional
import cv2

import backend.app.core.config as config
from backend.app.services.detection.focus_monitor import FocusMonitor
from backend.app.services.detection.yolo_service import YOLOService
from backend.app.services.audio.audio_alerts import CentralAudioManager
from backend.app.services.decision.state_machine import StudyState, STATE_DISPLAY


def draw_hud(
    frame: cv2.typing.MatLike,
    state: StudyState,
    monitor: FocusMonitor,
    fps: float,
    duration: float = 0.0,
    yolo_info: Optional[Dict[str, Any]] = None,
) -> None:
    """Render informative HUD and bounding boxes on the OpenCV camera frame."""
    h, w = frame.shape[:2]
    # STATE_DISPLAY values are tuples: (label_str, bgr_color_tuple)
    disp = STATE_DISPLAY.get(state)
    if disp is not None:
        label, color = disp[0], disp[1]
    else:
        label, color = state.name, (128, 128, 128)

    # Draw YOLO detected object indicators if enabled
    if getattr(config, "SHOW_YOLO_BOXES", True) and yolo_info:
        if yolo_info.get("person_detected") and yolo_info.get("person_box"):
            x1, y1, x2, y2 = [int(v) for v in yolo_info["person_box"]]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (200, 200, 200), 1)

        if yolo_info.get("phone_detected") and yolo_info.get("phone_box"):
            px1, py1, px2, py2 = [int(v) for v in yolo_info["phone_box"]]
            cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 0, 255), 2)
            cv2.putText(frame, "PHONE", (px1, max(20, py1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    # Draw face/shoulder landmarks
    if getattr(config, "SHOW_LANDMARKS", True):
        monitor.draw_landmarks(frame)

    # Top banner background
    cv2.rectangle(frame, (0, 0), (w, 55), (20, 20, 20), -1)
    cv2.line(frame, (0, 55), (w, 55), color, 2)

    # Status title & state duration
    diag_flag = " [DIAGNOSTIC - AUDIO MUTED]" if getattr(config, "DIAGNOSTIC_MODE", False) else ""
    cv2.putText(frame, f"STATE: {label} ({duration:.1f}s){diag_flag}", (15, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2, cv2.LINE_AA)
    cv2.putText(frame, f"{fps:.1f} FPS", (w - 120, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)

    # Real-Time Diagnostic & Evidence Panel (Right Side)
    f = monitor.last_features
    dec = monitor.last_decision
    if getattr(config, "SHOW_DEBUG_OVERLAY", True) and f:
        panel_w = 340
        panel_h = 175
        px1 = w - panel_w - 10
        py1 = 65
        cv2.rectangle(frame, (px1, py1), (px1 + panel_w, py1 + panel_h), (15, 15, 15), -1)
        cv2.rectangle(frame, (px1, py1), (px1 + panel_w, py1 + panel_h), (60, 60, 60), 1)

        l_ear = f.left_ear if f.left_ear is not None else 0.0
        r_ear = f.right_ear if f.right_ear is not None else 0.0
        avg_ear = f.ear if f.ear is not None else 0.0
        blink = f.blink_score if f.blink_score is not None else 0.0
        eye_st = f.eye_state.name if hasattr(f.eye_state, "name") else str(f.eye_state)
        if getattr(f.pose_features, "normal_blinking", False):
            eye_st = "BLINK (NORMAL)"

        lm_valid = "VALID" if getattr(f, "landmark_validity", False) else "INVALID/OCCLUDED"
        face_vis = "PRESENT" if f.face_detected else "HIDDEN/ABSENT"
        y_dur = f.eye_closure_duration if hasattr(f, "eye_closure_duration") else 0.0
        drowsy_ev = getattr(f, "drowsiness_evidence", "none")
        yaw_val = f.head_yaw if f.head_yaw is not None else 0.0
        pitch_val = f.head_pitch if f.head_pitch is not None else 0.0

        alert_elig = "YES" if dec and dec.alert_eligible else "NO"
        if getattr(config, "DIAGNOSTIC_MODE", False):
            alert_elig = "MUTED (DIAG)"

        lines = [
            f"EAR: L={l_ear:.2f} R={r_ear:.2f} Avg={avg_ear:.2f} (Blink={blink:.2f})",
            f"Eyes: {eye_st} (Closed: {y_dur:.1f}s)",
            f"Face: {face_vis} | Mesh: {lm_valid}",
            f"Pose: Yaw={yaw_val:+.1f}deg, Pitch={pitch_val:+.1f}deg",
            f"Drowsiness Ev: {drowsy_ev[:28]}",
            f"Alert Eligible: {alert_elig}",
        ]
        for i, text in enumerate(lines):
            t_color = (0, 255, 180) if "VALID" in text or "YES" in text else (210, 210, 210)
            if "CLOSED" in text or "DROWSINESS" in text:
                t_color = (0, 165, 255)
            cv2.putText(frame, text, (px1 + 8, py1 + 20 + i * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.44, t_color, 1, cv2.LINE_AA)

    # Multi-modal telemetry panel at bottom
    cv2.rectangle(frame, (0, h - 45), (w, h), (20, 20, 20), -1)
    cv2.line(frame, (0, h - 45), (w, h - 45), (60, 60, 60), 1)

    obs = monitor.last_observation
    obs_text = "Tracking workspace..."
    if obs:
        head_dir = obs.head_direction.value.name if hasattr(getattr(obs.head_direction, "value", None), "name") else str(getattr(obs.head_direction, "value", "UNKNOWN"))
        eye_st = obs.eye_state.value.name if hasattr(getattr(obs.eye_state, "value", None), "name") else str(getattr(obs.eye_state, "value", "UNKNOWN"))
        act_obs = getattr(obs, "observable_study_activity", None)
        act_str = getattr(act_obs, "details", None) or "ACTIVE"
        obs_text = f"Head: {head_dir} | Eyes: {eye_st} | Activity: {act_str.upper()}"

    cv2.putText(frame, obs_text, (15, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv2.LINE_AA)


def main() -> None:
    print("=" * 60)
    print("  AI Study Focus Monitor — Local Native Mode (Mode A)")
    print(f"  Camera Index: {config.CAMERA_INDEX}")
    if getattr(config, "DIAGNOSTIC_MODE", False):
        print("  SAFE DIAGNOSTIC MODE: ACTIVE (All audio alerts suppressed)")
    print("  Press 'q' or 'ESC' in the camera window to stop.")
    print("=" * 60)

    # Open camera with DirectShow on Windows for zero-latency DirectShow capture
    backend_flag = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    cap = cv2.VideoCapture(config.CAMERA_INDEX, backend_flag)
    if not cap.isOpened() and backend_flag != cv2.CAP_ANY:
        cap = cv2.VideoCapture(config.CAMERA_INDEX)

    if not cap.isOpened():
        print(f"[Error] Could not open camera at index {config.CAMERA_INDEX}.")
        print("Please verify camera connection and Windows privacy permissions.")
        return

    # Set camera resolution and target FPS
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Allow camera sensor auto-exposure and white balance to stabilize
    for _ in range(6):
        cap.read()
        time.sleep(0.03)

    monitor = FocusMonitor()
    audio = CentralAudioManager()
    yolo_service = YOLOService.get_instance()

    frame_count = 0
    fps = 30.0
    start_time = time.monotonic()
    last_fps_time = start_time
    cached_yolo: Dict[str, Any] = {}

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("[Warning] Failed to grab frame. Retrying...")
                time.sleep(0.1)
                continue

            now = time.monotonic()
            frame_count += 1
            if now - last_fps_time >= 1.0:
                fps = frame_count / (now - last_fps_time)
                frame_count = 0
                last_fps_time = now

            # Stride-cached YOLO object inference
            stride = getattr(config, "YOLO_INFERENCE_STRIDE", 1)
            if frame_count % stride == 0 or frame_count <= 2:
                cached_yolo = yolo_service.detect(frame)

            # Process frame through multimodal perception & decision engine
            state, duration = monitor.process_frame(frame, timestamp=now, yolo_detections=cached_yolo)

            # Update audio alerts
            audio.update_state(state)

            # Draw HUD
            draw_hud(frame, state, monitor, fps, duration=duration, yolo_info=cached_yolo)

            cv2.imshow(config.WINDOW_TITLE, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q') or key == 27:
                print("\n[Local Mode] Stop requested by user.")
                break
            elif key == ord('d') or key == ord('D'):
                config.SHOW_DEBUG_OVERLAY = not getattr(config, "SHOW_DEBUG_OVERLAY", True)
                config.SHOW_LANDMARKS = getattr(config, "SHOW_DEBUG_OVERLAY", True)
                print(f"[Local Mode] Debug Landmark Overlay: {'ENABLED' if config.SHOW_DEBUG_OVERLAY else 'DISABLED'}")

    except Exception as e:
        print(f"\n[Local Mode] Unexpected runtime exception: {e}")
        raise
    finally:
        try:
            cap.release()
        except Exception:
            pass
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        try:
            audio.stop()
        except Exception:
            pass
        try:
            monitor.close()
        except Exception:
            pass
        print("[Local Mode] Resources released cleanly.")


if __name__ == "__main__":
    main()
