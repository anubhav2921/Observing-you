"""
backend/app/services/detection — Vision feature extraction and object detectors.
"""

from backend.app.services.detection.upper_body_detector import UpperBodyDetector
from backend.app.services.detection.yolo_service import YOLOService
from backend.app.services.detection.focus_monitor import FocusMonitor

__all__ = ["UpperBodyDetector", "YOLOService", "FocusMonitor"]

