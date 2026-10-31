"""
backend/app/schemas/requests.py — Incoming command and status models.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ClientCommand(BaseModel):
    """Client WebSocket control command."""
    action: str = Field(..., description="Action: start, stop, reset, ping, calibrate")
    session_id: Optional[str] = None
    calibration_data: Optional[Dict[str, Any]] = None


class SessionStatus(BaseModel):
    """Session health and throughput metadata."""
    session_id: str
    active: bool
    fps: float
    frames_processed: int
    uptime_seconds: float
    current_state: str

