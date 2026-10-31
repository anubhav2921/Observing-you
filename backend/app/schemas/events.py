"""
backend/app/schemas/events.py — Structured Pydantic event models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RecommendationData(BaseModel):
    """Actionable, empathetic guidance with reason."""
    title: str = Field(..., description="Short summary title")
    message: str = Field(..., description="Actionable, non-shaming guidance")
    reason: str = Field(..., description="Technical or observation reason")
    severity: str = Field("info", description="Severity: positive, info, neutral, warning, critical")


class AlertData(BaseModel):
    """Centralized alert status and audio clip routing."""
    active: bool = Field(False, description="Whether alert is triggered")
    name: Optional[str] = Field(None, description="Active alert name")
    priority: Optional[int] = Field(None, description="Priority rank (1=highest, 5=lowest)")
    audio_file: Optional[str] = Field(None, description="URL or path to audio clip")
    reason: Optional[str] = Field(None, description="Trigger or suppression reason")


class ObservationData(BaseModel):
    """Independent multi-modal behavioral observations."""
    face_present: bool = False
    face_occluded: bool = False
    person_present: bool = True
    head_direction: str = "FACING_SCREEN"
    eye_state: str = "OPEN"
    ear: float = 0.0
    observable_study_activity: str = "SCREEN"
    inactivity_duration: float = 0.0
    hand_near_face: bool = False
    camera_health: str = "OK"
    detection_confidence: float = 1.0
    mouth_open_yawn: bool = False
    head_pitch_deg: float = 0.0
    head_yaw_deg: float = 0.0
    posture_name: str = "UPRIGHT"
    book_present: bool = False
    phone_present: bool = False
    phone_status: str = "NONE"
    behavior_category: str = "PRODUCTIVE_STUDYING"
    laptop_present: bool = False
    face_box: Optional[List[int]] = None
    focus_level: float = 0.85
    attention_level: float = 0.80
    distraction_level: float = 0.10
    drowsiness_level: float = 0.05


class DecisionRationale(BaseModel):
    """Structured breakdown: WHY DID THE AI MAKE THIS DECISION?"""
    primary_observation: str = Field(..., description="Primary anchor observation")
    additional_evidence: List[str] = Field(default_factory=list, description="Supporting evidence items")
    decision: str = Field(..., description="Classification output")
    audio_action: str = Field(..., description="Alert audio action")


class StateUpdateEvent(BaseModel):
    """Per-frame authoritative state event emitted to clients."""
    session_id: str
    timestamp: float
    frame_id: int
    state: str
    state_display: str
    state_color: List[int]
    confidence: float
    duration_seconds: float
    observations: ObservationData
    active_behaviors: List[str]
    diagnostic_reason: str
    alert: AlertData
    recommendation: RecommendationData
    decision_rationale: Optional[DecisionRationale] = None
    activity_label: str = "STUDYING"
    confirmation_status: str = "CONFIRMED"

