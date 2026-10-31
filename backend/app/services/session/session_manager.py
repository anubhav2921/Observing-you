"""
backend/app/services/session/session_manager.py — Registry for active monitoring sessions.
"""

from __future__ import annotations

import time
from typing import Dict, Optional
from backend.app.pipelines.session_pipeline import SessionPipeline


class SessionManager:
    """Manages concurrent monitoring session lifecycles."""

    def __init__(self) -> None:
        self.active_sessions: Dict[str, SessionPipeline] = {}
        self.created_at = time.monotonic()

    def get_or_create(self, session_id: Optional[str] = None) -> SessionPipeline:
        if session_id and session_id in self.active_sessions:
            return self.active_sessions[session_id]
        session = SessionPipeline(session_id=session_id)
        self.active_sessions[session.session_id] = session
        return session

    def remove(self, session_id: str) -> Optional[SessionPipeline]:
        session = self.active_sessions.pop(session_id, None)
        if session:
            session.close()
        return session

    def reset_session(self, session_id: str) -> bool:
        if session_id in self.active_sessions:
            self.active_sessions[session_id].reset()
            return True
        return False

    @property
    def count(self) -> int:
        return len(self.active_sessions)

