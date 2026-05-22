from typing import Optional
import json

import asyncpg
from app.models import UserContext


async def audit(
    conn: asyncpg.Connection,
    user: UserContext,
    action: str,
    resource: str,
    detail: Optional[dict] = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO audit_logs
            (tenant_id, user_id, user_email, role, action, resource, detail)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        """,
        user.tenant_id,
        user.user_id,
        user.email,
        user.role,
        action,
        resource,
        json.dumps(detail or {}),
    )
