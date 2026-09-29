"""
NetGuard AI — WebSocket live feed (api/ws.py)

A single endpoint, /ws/flows, that pushes every classified flow and every
raised/updated alert to all connected dashboard clients. No Socket.io —
this is FastAPI's native WebSocket support, per the tech-stack decision.

Every message carries a "type" field so the dashboard can route it:
  {"type": "flow",  ...}   -> one classified flow (live or batch)
  {"type": "alert", ...}   -> a new or updated alert

api/ingest (a later branch) will call broadcast_flow()/broadcast_alert()
right after it classifies a flow and runs it through the alert engine.
This module has zero knowledge of inference or the alert engine — it only
knows how to fan a dict out to whoever is listening.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("netguard.ws")

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """
    Tracks connected dashboard clients and broadcasts to all of them.

    A single instance (`manager`, below) is shared for the whole process.
    If sending to one client fails (closed tab, dropped connection), that
    client is removed and the broadcast continues for everyone else —
    one bad connection must never take down the live feed for the rest
    of the dashboard's viewers.
    """

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("Dashboard client connected (%d total)", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("Dashboard client disconnected (%d total)", len(self.active_connections))

    async def _broadcast(self, payload: Dict[str, Any]) -> None:
        dead: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)

    async def broadcast_flow(self, flow: Dict[str, Any]) -> None:
        """flow must already contain id, src_ip, dst_ip, label, confidence, timestamp."""
        await self._broadcast({"type": "flow", **flow})

    async def broadcast_alert(self, alert: Dict[str, Any]) -> None:
        """alert must already contain id, src_ip, label, confidence, flow_count, status, timestamp."""
        await self._broadcast({"type": "alert", **alert})


# Single shared instance — import THIS from api/ingest later, don't
# instantiate a second ConnectionManager anywhere.
manager = ConnectionManager()


@router.websocket("/ws/flows")
async def flows_websocket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # The dashboard doesn't send anything meaningful on this socket
            # today — this just keeps the connection open and lets us
            # detect a disconnect promptly. If the dashboard ever needs to
            # send commands (e.g. "acknowledge alert"), handle `data` here.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)