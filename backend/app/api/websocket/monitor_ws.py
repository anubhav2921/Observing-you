"""
backend/app/api/websocket/monitor_ws.py — Bi-directional video streaming and state updates.
"""

from __future__ import annotations

import json
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.pipelines.session_pipeline import SessionPipeline
from backend.app.services.decision.state_machine import StudyState

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/monitor")
async def websocket_monitor_endpoint(websocket: WebSocket) -> None:
    """Bi-directional real-time stream. Receives JPEG blobs, emits StateUpdateEvent JSON."""
    await websocket.accept()
    session = SessionPipeline()
    print(f"[WebSocket] Connected session: {session.session_id}")

    try:
        # Initial handshake event
        init_event = session._build_event_from_decision(
            time.monotonic(),
            StudyState.STUDYING,
            None,
            None,
        )
        await websocket.send_json(init_event.model_dump())

        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message and message["bytes"]:
                raw_bytes = message["bytes"]
                event = session.process_frame_bytes(raw_bytes)
                await websocket.send_json(event.model_dump())

            elif "text" in message and message["text"]:
                text_data = message["text"]
                if "reset" in text_data:
                    session.reset()
                    await websocket.send_json({"type": "info", "message": "Session reset successful."})
                elif "ping" in text_data:
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})
                elif "calibrate" in text_data:
                    try:
                        cmd = json.loads(text_data)
                        if cmd.get("action") == "calibrate":
                            session.apply_calibration(cmd.get("calibration_data", {}))
                            await websocket.send_json({"type": "info", "message": "Calibration profile applied successfully."})
                    except Exception:
                        pass

    except WebSocketDisconnect:
        print(f"[WebSocket] Disconnected session: {session.session_id}")
    except Exception as e:
        print(f"[WebSocket] Session error ({session.session_id}): {e}")
    finally:
        session.close()
        print(f"[WebSocket] Cleaned up session: {session.session_id}")

