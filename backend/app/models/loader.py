"""
backend/app/models/loader.py — Unified loader for YOLO and MediaPipe models.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import backend.app.core.config as config


def verify_model_files() -> dict[str, bool]:
    """Check existence of all required vision task files."""
    return {
        "yolov8": os.path.isfile(config.YOLO_WEIGHTS),
        "face_landmarker": os.path.isfile(config.FACE_LANDMARKER_MODEL),
        "pose_landmarker": os.path.isfile(config.POSE_LANDMARKER_MODEL),
        "hand_landmarker": os.path.isfile(config.HAND_LANDMARKER_MODEL),
    }

