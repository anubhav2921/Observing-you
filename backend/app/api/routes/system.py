"""
backend/app/api/routes/system.py — System health and configuration routes.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi import APIRouter

import backend.app.core.config as config
from backend.app.services.detection.yolo_service import YOLOService
from backend.app.models.loader import verify_model_files

router = APIRouter(tags=["System"])
SERVER_START_TIME = time.monotonic()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Return backend health, hardware acceleration, and model status."""
    yolo_svc = YOLOService.get_instance()
    return {
        "status": "healthy",
        "uptime_seconds": round(time.monotonic() - SERVER_START_TIME, 1),
        "device": yolo_svc.device,
        "yolo_loaded": yolo_svc.model is not None,
        "media_pipe_tasks": verify_model_files(),
    }


@router.get("/config")
async def get_system_config() -> Dict[str, Any]:
    """Expose non-sensitive engine thresholds and durations."""
    return {
        "distraction_threshold_sec": getattr(config, "PHONE_DETECT_SECS", 4.0),
        "inactivity_threshold_sec": getattr(config, "INACTIVITY_WARNING_SECS", 12.0),
        "occlusion_threshold_sec": getattr(config, "FACE_OCCLUDED_SECS", 3.5),
        "drowsiness_threshold_sec": getattr(config, "DROWSINESS_SUSTAINED_SECS", 1.8),
        "absence_threshold_sec": getattr(config, "STUDENT_ABSENT_SECS", 6.0),
        "recovery_threshold_sec": getattr(config, "RECOVERY_STABILITY_SECS", 1.2),
        "alert_cooldown_sec": getattr(config, "ALERT_COOLDOWN_SECONDS", 15.0),
        "ear_threshold": getattr(config, "EAR_CLOSE_THRESHOLD", 0.20),
    }

