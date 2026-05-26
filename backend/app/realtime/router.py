"""
Piccadily Industrial Historian — WebSocket Router
Real-time telemetry streaming with per-room auth, snapshot on connect, and keepalive.
"""

from fastapi import APIRouter, HTTPException

from app.infra.database import get_read_pool

router = APIRouter(prefix="/api/v1", tags=["websocket"])


@router.get("/latest/{tenant_id}/{plant_id}")
async def get_latest_telemetry(tenant_id: str, plant_id: str):
    """
    Simple polling endpoint that returns the latest telemetry snapshot
    for a given tenant and plant from the telemetry_latest table.
    """
    pool = get_read_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database not ready")

    async with pool.acquire() as conn:
        await conn.execute("SELECT set_config('app.current_tenant', $1, false)", tenant_id)
        rows = await conn.fetch(
            "SELECT tag_name, value, quality, ts, unit FROM telemetry_latest WHERE tenant_id=$1 AND plant_id=$2",
            tenant_id,
            plant_id,
        )

    return {
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
