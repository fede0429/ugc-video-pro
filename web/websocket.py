"""
web/websocket.py
================
WebSocket connection manager and endpoint for real-time progress updates.

Architecture:
    ConnectionManager maintains a dict of task_id → set[WebSocket].
    The background task (tasks.py) calls manager.broadcast() to push
    JSON messages to all clients subscribed to a given task.

WebSocket endpoint:
    /api/ws/progress/{task_id}

Authentication:
    The client must pass the access token either:
        (a) as a query parameter: ?token=<access_token>
        (b) as the first text message after connecting

Message format: see schemas.ProgressUpdate
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError

from web.auth import decode_token

logger = logging.getLogger(__name__)

# ── Global singleton manager ────────────────────────────────────────────────────────
# Instantiated once in app.py and reused across all modules.

class ConnectionManager:
    """
    Manages active WebSocket connections keyed by task_id.

    Thread-safety: All FastAPI WebSocket handlers run on the same asyncio
    event loop, so a plain dict + set is safe here.
    """

    def __init__(self) -> None:
        # task_id → set of connected WebSocket objects
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and register it for task_id."""
        await websocket.accept()
        if task_id not in self._connections:
            self._connections[task_id] = set()
        self._connections[task_id].add(websocket)
        logger.info(f"WS connected: task={task_id} total={len(self._connections[task_id])}")

    def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket from the task's connection set."""
        if task_id in self._connections:
            self._connections[task_id].discard(websocket)
            if not self._connections[task_id]:
                del self._connections[task_id]
        logger.info(f"WS disconnected: task={task_id}")

    async def broadcast(self, task_id: str, data: dict) -> None:
        """
        Send a JSON message to all clients subscribed to task_id.

        Silently removes any dead connections encountered during the send.
        """
        if task_id not in self._connections:
            logger.info(f"WS broadcast: no subscribers for task={task_id}")
            return

        dead: list[WebSocket] = []
        for ws in list(self._connections[task_id]):
            try:
                await ws.send_json(data)
                logger.info(f"WS broadcast OK: task={task_id} event={data.get('event')} stage={data.get('stage', '-')}")
            except Exception as exc:
                logger.warning(f"WS send failed (task={task_id}): {exc}")
                dead.append(ws)

        for ws in dead:
            self.disconnect(task_id, ws)

    def has_subscribers(self, task_id: str) -> bool:
        """Return True if at least one client is subscribed for task_id."""
        return bool(self._connections.get(task_id))

    def subscriber_count(self, task_id: str) -> int:
        return len(self._connections.get(task_id, set()))


# ── Module-level singleton (imported by tasks.py and app.py) ───────────────────────────
manager = ConnectionManager()


# ── WebSocket router ───────────────────────────────────────────────────────────────────
router = APIRouter(tags=["websocket"])


@router.websocket("/progress/{task_id}")
async def ws_progress(
    task_id: str,
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
) -> None:
    """
    WebSocket endpoint for real-time video generation progress.

    URL: /api/ws/progress/{task_id}?token=<access_token>

    The client may also send the token as the first text frame after
    connecting (useful when query-string tokens are inconvenient).

    Once authenticated, the server keeps the connection open and pushes
    ProgressUpdate JSON objects whenever the background task sends them.
    The connection is closed by the server when the task completes or fails,
    or by the client at any time.
    """
    # ── Authenticate ───────────────────────────────────────────────────────────────
    if token is None:
        # Ask the client to send the token as the first message
        await websocket.accept()
        try:
            token = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        except asyncio.TimeoutError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Decode without re-accepting (already accepted)
        try:
            decode_token(token, expected_type="access")
        except Exception:
            await websocket.send_json({"event": "error", "error": "Invalid token"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Register on the already-accepted socket
        if task_id not in manager._connections:
            manager._connections[task_id] = set()
        manager._connections[task_id].add(websocket)
        logger.info(f"WS auth via message: task={task_id}")

    else:
        # Validate query-string token before accepting
        try:
            decode_token(token, expected_type="access")
        except Exception:
            # Must accept before closing per the WS spec
            await websocket.accept()
            await websocket.send_json({"event": "error", "error": "Invalid token"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await manager.connect(task_id, websocket)

    # ── Keep-alive loop (FIXED: proper infinite loop with ping/pong) ──────────────
    try:
        while True:
            try:
                # Wait for any client message (ping / disconnect)
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle ping from client (may be plain "ping" or JSON '"ping"')
                msg_clean = msg.strip().strip('"')
                if msg_clean == "ping":
                    await websocket.send_json({"event": "pong"})
            except asyncio.TimeoutError:
                # No message from client in 30s — send a server ping to keep alive
                try:
                    await websocket.send_json({"event": "ping"})
                except Exception:
                    # Connection dead, break out
                    break
    except WebSocketDisconnect:
        logger.info(f"WS client disconnected: task={task_id}")
    except Exception as exc:
        logger.warning(f"WS unexpected error (task={task_id}): {exc}")
    finally:
        manager.disconnect(task_id, websocket)


# ── Convenience function (used by tasks.py) ────────────────────────────────────────────
async def broadcast_progress(task_id: str, data: dict) -> None:
    """Convenience wrapper so tasks.py can do: from web.websocket import broadcast_progress"""
    await manager.broadcast(task_id, data)
