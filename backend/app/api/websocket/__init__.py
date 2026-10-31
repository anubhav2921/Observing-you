"""
backend/app/api/websocket — WebSocket streaming endpoints.
"""

from backend.app.api.websocket.monitor_ws import router as ws_router

__all__ = ["ws_router"]

