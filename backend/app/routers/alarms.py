"""
Piccadily Industrial Historian — Alarm Router
Active alarms, acknowledgement, clearing, history, and summary endpoints.
"""

import asyncio
from datetime import datetime
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import audit, get_current_user, require_role
from ..broadcaster import ws_manager
from ..database import get_db
from ..models import AlarmAckRequest, AlarmClearRequest, UserContext

router = APIRouter(prefix="/api/v1/alarms", tags=["alarms"])


@router.get("/active")
async def get_active_alarms(
    plant_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    q = (
        "SELECT alarm_id, plant_id, tag_name, severity, message, "
        "trigger_value, occurred_at, alarm_state, acked_by, acked_at "
        "FROM alarms WHERE tenant_id=$1 AND alarm_state != 'CLEARED'"
    )
    params: list = [user.tenant_id]
    if plant_id:
        params.append(plant_id)
        q += f" AND plant_id=${len(params)}"
    if severity:
        params.append(severity.upper())
        q += f" AND severity=${len(params)}"
    q += " ORDER BY occurred_at DESC LIMIT 200"
    rows = await conn.fetch(q, *params)
    return {"count": len(rows), "alarms": [dict(r) for r in rows]}


@router.post("/ack")
async def acknowledge_alarm(
    req: AlarmAckRequest,
    user: UserContext = Depends(require_role("admin", "engineer", "operator")),
    conn: asyncpg.Connection = Depends(get_db),
):
    # Fetch plant_id BEFORE update for correct WS routing
    alarm_row = await conn.fetchrow(
        "SELECT plant_id FROM alarms WHERE alarm_id=$1 AND tenant_id=$2",
        req.alarm_id,
        user.tenant_id,
    )
    if not alarm_row:
        raise HTTPException(404, "Alarm not found")

    result = await conn.execute(
        "UPDATE alarms SET alarm_state='ACKNOWLEDGED', acked_by=$1, acked_at=now() "
        "WHERE alarm_id=$2 AND tenant_id=$3 AND alarm_state='ACTIVE'",
        req.acked_by,
        req.alarm_id,
        user.tenant_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(409, "Alarm already acknowledged or cleared")

    await conn.execute(
        "INSERT INTO alarm_history (alarm_id, tenant_id, action, performed_by, comment) "
        "VALUES ($1,$2,'ACKNOWLEDGED',$3,$4)",
        req.alarm_id,
        user.tenant_id,
        req.acked_by,
        req.comment,
    )
    await audit(conn, user, "ACK_ALARM", f"alarms/{req.alarm_id}", {"comment": req.comment})

    plant_id = alarm_row["plant_id"]
    asyncio.create_task(
        ws_manager.broadcast(
            user.tenant_id,
            plant_id,
            {"type": "alarm_ack", "alarm_id": str(req.alarm_id), "plant_id": plant_id, "acked_by": req.acked_by},
        )
    )
    return {"ok": True, "alarm_id": str(req.alarm_id)}


@router.post("/clear")
async def clear_alarms(
    req: AlarmClearRequest,
    user: UserContext = Depends(require_role("admin", "engineer", "operator")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Bulk-clear acknowledged alarms."""
    if req.alarm_ids:
        result = await conn.execute(
            "UPDATE alarms SET alarm_state='CLEARED' "
            "WHERE tenant_id=$1 AND plant_id=$2 AND alarm_id = ANY($3::uuid[]) "
            "AND alarm_state='ACKNOWLEDGED'",
            user.tenant_id,
            req.plant_id,
            [str(aid) for aid in req.alarm_ids],
        )
    else:
        result = await conn.execute(
            "UPDATE alarms SET alarm_state='CLEARED' WHERE tenant_id=$1 AND plant_id=$2 AND alarm_state='ACKNOWLEDGED'",
            user.tenant_id,
            req.plant_id,
        )
    cleared_count = int(result.split()[-1])
    await audit(
        conn, user, "CLEAR_ALARMS", f"plants/{req.plant_id}", {"cleared": cleared_count, "comment": req.comment}
    )
    asyncio.create_task(
        ws_manager.broadcast(
            user.tenant_id,
            req.plant_id,
            {"type": "alarms_cleared", "plant_id": req.plant_id, "count": cleared_count, "cleared_by": req.cleared_by},
        )
    )
    return {"ok": True, "cleared": cleared_count}


@router.get("/history")
async def get_alarm_history(
    plant_id: Optional[str] = Query(None),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    severity: Optional[str] = Query(None),
    state: Optional[str] = Query(None, description="ACTIVE | ACKNOWLEDGED | CLEARED"),
    limit: int = Query(500, le=5000),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    q = "SELECT * FROM alarms WHERE tenant_id=$1"
    params: list = [user.tenant_id]
    if plant_id:
        params.append(plant_id)
        q += f" AND plant_id=${len(params)}"
    if start:
        params.append(start)
        q += f" AND occurred_at>=${len(params)}"
    if end:
        params.append(end)
        q += f" AND occurred_at<=${len(params)}"
    if severity:
        params.append(severity.upper())
        q += f" AND severity=${len(params)}"
    if state:
        params.append(state.upper())
        q += f" AND alarm_state=${len(params)}"
    params.append(limit)
    q += f" ORDER BY occurred_at DESC LIMIT ${len(params)}"
    rows = await conn.fetch(q, *params)
    return {"count": len(rows), "alarms": [dict(r) for r in rows]}


@router.get("/summary")
async def alarm_summary(
    plant_id: str = Query(...),
    hours: int = Query(24, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Alarm count by severity for the last N hours — dashboard KPI tiles."""
    rows = await conn.fetch(
        "SELECT severity, count(*) AS total, "
        "sum(CASE WHEN alarm_state='ACKNOWLEDGED' THEN 1 ELSE 0 END) AS acked, "
        "sum(CASE WHEN alarm_state='ACTIVE' THEN 1 ELSE 0 END) AS unacked, "
        "sum(CASE WHEN alarm_state='CLEARED' THEN 1 ELSE 0 END) AS cleared "
        "FROM alarms WHERE tenant_id=$1 AND plant_id=$2 "
        "AND occurred_at >= now() - ($3 || ' hours')::interval "
        "GROUP BY severity ORDER BY severity",
        user.tenant_id,
        plant_id,
        str(hours),
    )
    return {"plant_id": plant_id, "hours": hours, "summary": [dict(r) for r in rows]}
