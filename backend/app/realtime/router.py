"""
Piccadily Industrial Historian — WebSocket Router
Real-time telemetry streaming with per-room auth, snapshot on connect, and keepalive.
"""

import asyncio
from typing import Optional
import secrets
import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, Depends, HTTPException

from app.identity.auth import _verify_edge_api_key_db, require_permission, Permission
from app.realtime.broadcaster import ws_manager
from app.infra.database import get_read_pool
from app.models import UserContext

router = APIRouter(prefix="/api/v1", tags=["websocket"])


@router.post("/ws/ticket")
async def generate_ws_ticket(user: UserContext = Depends(require_permission(Permission.TELEMETRY_READ))):
    """
    Generate a short-lived, single-use ticket for WebSocket authentication.
    This prevents passing JWTs in query parameters (which leak in Nginx logs).
    """
    from app.telemetry.stream_writer import redis_client

    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable")

    ticket = secrets.token_urlsafe(32)
    user_data = user.model_dump()

    # Store ticket for 30 seconds
    await redis_client.set(f"ws:ticket:{ticket}", json.dumps(user_data), ex=30)
    return {"ticket": ticket}


@router.websocket("/ws/{tenant_id}/{plant_id}")
async def websocket_stream(
    websocket: WebSocket,
    tenant_id: str,
    plant_id: str,
    ticket: Optional[str] = Query(None),
    api_key: Optional[str] = Query(None),
):
    """
    Real-time telemetry stream for dashboards and SCADA clients.
    Auth: ?ticket=<Ticket UUID> OR ?api_key=<raw edge key>
    On connect: sends snapshot of telemetry_latest.
    Keepalive: client sends "ping" → server replies "pong".
               server sends "pong" every 30s if no client message.
    """
    # ── Auth ────────────────────────────────────────────────────────────────
    if api_key:
        t = await _verify_edge_api_key_db(api_key)
        if not t or t != tenant_id:
            await websocket.close(code=4401)
            return
    elif ticket:
        from app.telemetry.stream_writer import redis_client

        if not redis_client:
            await websocket.close(code=1011, reason="Redis unavailable")
            return

        data = await redis_client.get(f"ws:ticket:{ticket}")
        if not data:
            await websocket.close(code=4401, reason="Invalid or expired ticket")
            return

        await redis_client.delete(f"ws:ticket:{ticket}")

        user_dict = json.loads(data)
        t_id = user_dict.get("tenant_id")
        if t_id != tenant_id:
            await websocket.close(code=4403, reason="Tenant mismatch")
            return

        plant_ids = user_dict.get("plant_ids", [])
        if plant_ids and plant_id not in plant_ids:
            await websocket.close(code=4403, reason="Access denied to plant")
            return
    else:
        await websocket.close(code=4401)
        return

    await ws_manager.connect(websocket, tenant_id, plant_id)

    try:
        # Send current snapshot from telemetry_latest
        pool = get_read_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT tag_name, value, quality, ts, unit FROM telemetry_latest WHERE tenant_id=$1 AND plant_id=$2",
                tenant_id,
                plant_id,
            )
        await websocket.send_json(
            {
                "type": "snapshot",
                "plant_id": plant_id,
                "count": len(rows),
                "data": {
                    r["tag_name"]: {
                        "v": r["value"],
                        "q": r["quality"],
                        "u": r["unit"],
                        "t": r["ts"].isoformat() if r["ts"] else None,
                    }
                    for r in rows
                },
            }
        )

        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("pong")  # server-initiated keepalive

    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket, tenant_id, plant_id)
