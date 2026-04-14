"""Live WebSocket router — real-time broadcast to connected clients."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["live"])


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "WebSocket connected. Active connections: %d",
            len(self.active_connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the active list."""
        self.active_connections.remove(websocket)
        logger.info(
            "WebSocket disconnected. Active connections: %d",
            len(self.active_connections),
        )

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to every connected client."""
        disconnected: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        # Clean up stale connections
        for conn in disconnected:
            self.active_connections.remove(conn)
            logger.warning("Removed stale WebSocket connection during broadcast")


manager = ConnectionManager()


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    """WebSocket endpoint for live data streaming."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; handle incoming messages if needed
            data = await websocket.receive_json()
            logger.debug("Received WS message: %s", data)
            # Echo back or handle commands as needed
            await websocket.send_json({"type": "ack", "received": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
        logger.exception("Unexpected error in WebSocket connection")
