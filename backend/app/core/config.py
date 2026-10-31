"""
backend/app/core/config.py — Central configuration for AI Study Focus Monitor.
Manages all timeouts, detection thresholds, hardware devices, and model paths.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path

# Repository root dynamically resolved relative to this config file
REPO_ROOT = Path(__file__).resolve().parents[3]
ASSETS_DIR = REPO_ROOT / "assets"
MODELS_DIR = ASSETS_DIR / "models"
AUDIO_DIR = ASSETS_DIR / "audio"
LOGS_DIR = REPO_ROOT / "logs"

os.makedirs(LOGS_DIR, exist_ok=True)

# ──────────────────────────────────────────────
#  Device & Camera
# ──────────────────────────────────────────────
DEVICE: str = "auto"           # "auto", "cuda", or "cpu"
CAMERA_INDEX: int = 0          # Default camera index
TARGET_FPS: int = 30           # Target capture frame rate
CAMERA_RETRY_ATTEMPTS: int = 3 # Number of reconnect attempts before CAMERA_ERROR
CAMERA_RETRY_DELAY_SEC: float = 0.5
FROZEN_FRAME_TIMEOUT_SEC: float = 2.0  # Max seconds identical frames indicate frozen feed
LOW_LIGHT_THRESHOLD: float = 18.0      # Average grayscale intensity threshold for LOW_VISIBILITY
OVEREXPOSURE_THRESHOLD: float = 245.0  # Average grayscale intensity threshold for washed out feed

# ──────────────────────────────────────────────
#  Model File Paths
# ──────────────────────────────────────────────
YOLO_WEIGHTS: str = str(MODELS_DIR / "yolov8n.pt") if (MODELS_DIR / "yolov8n.pt").is_file() else "yolov8n.pt"
FACE_LANDMARKER_MODEL: str = str(MODELS_DIR / "face_landmarker.task") if (MODELS_DIR / "face_landmarker.task").is_file() else "face_landmarker.task"
POSE_LANDMARKER_MODEL: str = str(MODELS_DIR / "pose_landmarker.task") if (MODELS_DIR / "pose_landmarker.task").is_file() else "pose_landmarker.task"
HAND_LANDMARKER_MODEL: str = str(MODELS_DIR / "hand_landmarker.task") if (MODELS_DIR / "hand_landmarker.task").is_file() else "hand_landmarker.task"

# ──────────────────────────────────────────────
#  YOLO & Object Detection Thresholds
# ──────────────────────────────────────────────
YOLO_CONF_THRESHOLD: float = 0.40
YOLO_CONF: float = 0.40
YOLO_IOU_THRESHOLD: float = 0.45
YOLO_INFERENCE_STRIDE: int = 1  # 1 = every frame, >1 = cached strides

# COCO Class IDs
COCO_PERSON: int = 0
COCO_CELL_PHONE: int = 67
COCO_BOOK: int = 73
COCO_LAPTOP: int = 63

# ──────────────────────────────────────────────
#  Focus-state durations & thresholds (in seconds)
# ──────────────────────────────────────────────
# 1. Student absence: No person detected in frame
STUDENT_ABSENT_SECS: float = 6.0

# 2. Face occlusion: Person present, face deliberately covered/obscured
FACE_OCCLUDED_SECS: float = 3.5
FACE_OCCLUSION_IOU_THRESHOLD: float = 0.25

# 3. Reading posture tolerances
READING_PITCH_MIN_DEG: float = 10.0
READING_PITCH_MAX_DEG: float = 38.0
READING_YAW_MAX_DEG: float = 22.0

# 4. Looking away: Gaze / head yaw turned sideways
HEAD_YAW_THRESHOLD_DEG: float = 25.0
LOOKING_AWAY_SECS: float = 8.0

# 5. Inactivity & Camera staring:
CAMERA_STARING_UNCONFIRMED_SECS: float = 3.5
INACTIVITY_WARNING_SECS: float = 12.0
MOTION_STILL_THRESHOLD: float = 0.006

# 6. Phone distraction & Active usage policy:
PHONE_VISIBLE_SECS: float = 2.5            # Mere phone visible on desk without handling
PHONE_ACTIVE_USAGE_SECS: float = 0.8       # Fast 0.5–1.0s trigger when actively handled / gaze directed
PHONE_DETECT_SECS: float = 0.8             # Standard active phone confirmation
HEAD_TURN_ROOM_SCAN_YAW_DEG: float = 30.0  # Clear room scan yaw swing (not monitor glance)

# 7. Sleepiness & Drowsiness & Eye Calibration:
BASELINE_OPEN_EAR: float = 0.28            # Calibrated or default open-eye EAR
EAR_CLOSE_THRESHOLD: float = 0.19          # Absolute minimum closure threshold
BORDERLINE_EAR_THRESHOLD: float = 0.22     # Fatigued / squinting threshold
BLINK_BLENDSHAPE_THRESHOLD: float = 0.58   # MediaPipe neural blendshape blink threshold (0.0=open, 1.0=closed)
DROWSINESS_SUSTAINED_SECS: float = 2.0     # Sustained continuous closure required for sleep alert
BRIEF_BLINK_MAX_SECS: float = 0.5          # Blinks under this are classified as normal blinking
HEAD_PITCH_DROOP_DEG: float = 25.0         # Pitch droop angle
HEAD_DROOP_CYCLIC_PITCH_DEG: float = 26.0  # Cyclic fatigue nodding droop threshold
DROOP_SUSTAINED_SECS: float = 2.0          # Sustained droop duration

# 8. Recovery & Hysteresis (Separate conditions per alert category):
RECOVERY_STABILITY_SECS: float = 1.8       # General fallback stability
RECOVERY_DROWSINESS_SECS: float = 2.5      # Must keep eyes open and upright
RECOVERY_DISTRACTION_SECS: float = 1.8     # Must look at screen/reading material without phone
RECOVERY_OCCLUSION_SECS: float = 1.5       # Must have face clearly visible
RECOVERY_ABSENCE_SECS: float = 2.0         # Must have student continuously present

# 9. Rolling time window for smoothing noisy detections
SMOOTHING_WINDOW_SECS: float = 0.5
MIN_STATE_CONSENSUS_RATIO: float = 0.55

# ──────────────────────────────────────────────
#  Audio Alerts
# ──────────────────────────────────────────────
AUDIO_ENABLED: bool = True
DIAGNOSTIC_MODE: bool = False  # When True: runs all detection & logging, but suppresses audio alerts

def _find_audio_file(pattern: str, default_name: str) -> str:
    matches = glob.glob(str(AUDIO_DIR / pattern)) or glob.glob(str(REPO_ROOT / pattern))
    if matches:
        return matches[0]
    return str(AUDIO_DIR / default_name)

AUDIO_DISTRACTION_FILE: str = _find_audio_file("*IAS*.mp3", "distraction_alert.mp3")
AUDIO_SLEEPINESS_FILE: str  = _find_audio_file("*uth*.mp3", "drowsiness_alert.mp3")
AUDIO_OCCLUSION_FILE: str   = _find_audio_file("*InShot*.mp3*", "occlusion_alert.mp3")
AUDIO_CAMERA_ERROR_FILE: str = ""
AUDIO_ABSENT_FILE: str = ""

ALERT_COOLDOWN_SECONDS: float = 15.0

DISTRACTION_ALERT_ENABLED: bool = True
SLEEPINESS_ALERT_ENABLED: bool  = True
CAMERA_ERROR_ALERT_ENABLED: bool = True
OCCLUSION_ALERT_ENABLED: bool = True

# ──────────────────────────────────────────────
#  Logging & Debugging
# ──────────────────────────────────────────────
LOG_TRANSITIONS: bool = True
LOG_FILE_PATH: str = str(LOGS_DIR / "study_monitor.log")
DEBUG_METRICS: bool = True
RECORD_SESSION: bool = False
RECORD_OUTPUT_PATH: str = "debug_session_recording.avi"

# ──────────────────────────────────────────────
#  HUD / Visual Display
# ──────────────────────────────────────────────
SHOW_LANDMARKS: bool = True
SHOW_YOLO_BOXES: bool = True
SHOW_DEBUG_OVERLAY: bool = True
WINDOW_TITLE: str = "AI Study Focus Monitor"

