"""
Piccadily Industrial Historian — WebSocket Router
Real-time telemetry streaming with per-room auth, snapshot on connect, and keepalive.
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from ..auth import _decode_supabase_jwt, _verify_edge_api_key_db
from ..broadcaster import ws_manager
from ..database import get_pool

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{tenant_id}/{plant_id}")
async def websocket_stream(
    websocket: WebSocket,
    tenant_id: str,
    plant_id: str,
    token: Optional[str] = Query(None),
    api_key: Optional[str] = Query(None),
):
    """
    Real-time telemetry stream for dashboards and SCADA clients.
    Auth: ?token=<Supabase JWT> OR ?api_key=<raw edge key>
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
    elif token:
        try:
            payload = _decode_supabase_jwt(token)
            meta = payload.get("app_metadata", {})
            if meta.get("tenant_id") != tenant_id:
                await websocket.close(code=4403)
                return
        except Exception:
            await websocket.close(code=4401)
            return
    else:
        await websocket.close(code=4401)
        return

    await ws_manager.connect(websocket, tenant_id, plant_id)

    try:
        # Send current snapshot from telemetry_latest
        pool = get_pool()
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
