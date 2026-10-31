"""
backend/app/core/logging.py — Structured JSONL diagnostic logging.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional


class StructuredLogger:
    """Logs structured state transitions and frame diagnostics in JSONL format."""

    def __init__(self, log_path: str = "logs/study_monitor.log", enabled: bool = True) -> None:
        self.enabled = enabled
        self.log_path = log_path
        if self.enabled:
            os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)

    def log_transition(
        self,
        prev_state: str,
        new_state: str,
        trigger_condition: str,
        confidence: float,
        elapsed_duration: float,
        detector_outputs: Dict[str, Any],
    ) -> None:
        if not self.enabled:
            return
        record = {
            "type": "TRANSITION",
            "timestamp": time.time(),
            "prev_state": prev_state,
            "new_state": new_state,
            "trigger_condition": trigger_condition,
            "confidence": round(confidence, 3),
            "elapsed_seconds": round(elapsed_duration, 2),
            "detector_outputs": detector_outputs,
        }
        self._write_line(record)

    def log_diagnostic(
        self,
        frame_idx: int,
        timestamp: float,
        camera_health: str,
        state: str,
        duration: float,
        confidence: float,
        observations: Dict[str, Any],
        alert_eligible: bool,
        alert_rejection_reason: Optional[str] = None,
        raw_predictions: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled:
            return
        record = {
            "type": "DIAGNOSTIC",
            "frame_idx": frame_idx,
            "timestamp": timestamp,
            "camera_health": camera_health,
            "state": state,
            "duration": round(duration, 2),
            "confidence": round(confidence, 3),
            "alert_eligible": alert_eligible,
            "alert_rejection_reason": alert_rejection_reason,
            "observations": observations,
            "raw_predictions": raw_predictions or {},
        }
        self._write_line(record)

    def _write_line(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            print(f"[StructuredLogger Error] {e}")

