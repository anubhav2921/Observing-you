"""
backend/app/api/routes/session.py — Session management REST endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from backend.app.schemas.requests import ClientCommand
from backend.app.services.session.session_manager import SessionManager

router = APIRouter(prefix="/session", tags=["Session"])
session_manager = SessionManager()


@router.post("/reset")
async def reset_session(cmd: ClientCommand) -> JSONResponse:
    """Reset a specific monitoring session by session_id."""
    sid = cmd.session_id
    if sid and session_manager.reset_session(sid):
        return JSONResponse({"status": "success", "message": f"Session {sid} reset."})
    return JSONResponse(
        {"status": "error", "message": "Session not found or unspecified."},
        status_code=status.HTTP_404_NOT_FOUND,
    )

