from enum import Enum
from functools import lru_cache
from typing import Set

from fastapi import Depends, HTTPException
from app.models import UserContext
from app.identity.auth import get_current_user


class Permission(str, Enum):
    TELEMETRY_READ = "telemetry:read"
    TELEMETRY_WRITE = "telemetry:write"
    ALARMS_READ = "alarms:read"
    ALARMS_ACK = "alarms:ack"
    ALARMS_CONFIG = "alarms:config"
    METADATA_READ = "metadata:read"
    METADATA_WRITE = "metadata:write"
    ADMIN_USERS = "admin:users"
    ADMIN_API_KEYS = "admin:api_keys"
    ADMIN_FULL = "admin:full"


ROLE_PERMISSIONS: dict[str, Set[Permission]] = {
    "viewer": {
        Permission.TELEMETRY_READ,
        Permission.ALARMS_READ,
        Permission.METADATA_READ,
    },
    "operator": {
        Permission.TELEMETRY_READ,
        Permission.ALARMS_READ,
        Permission.ALARMS_ACK,
        Permission.METADATA_READ,
    },
    "engineer": {
        Permission.TELEMETRY_READ,
        Permission.ALARMS_READ,
        Permission.ALARMS_ACK,
        Permission.ALARMS_CONFIG,
        Permission.METADATA_READ,
        Permission.METADATA_WRITE,
    },
    "admin": set(Permission),
    "edge_agent": {
        Permission.TELEMETRY_WRITE,
    },
}


@lru_cache()
def require_permission(perm: Permission):
    async def _guard(user: UserContext = Depends(get_current_user)) -> UserContext:
        user_perms = ROLE_PERMISSIONS.get(user.role, set())
        if perm not in user_perms:
            raise HTTPException(
                status_code=403,
                detail=f"Missing permission: {perm.value}. Current role '{user.role}' does not have this access.",
            )
        return user

    return _guard


async def require_plant_access(plant_id: str, user: UserContext = Depends(get_current_user)) -> UserContext:
    if user.is_edge:
        return user
    if user.plant_ids and plant_id not in user.plant_ids:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied to plant '{plant_id}'. Allowed plants: {user.plant_ids}",
        )
    if not user.plant_ids:
        from app.infra.database import get_read_pool

        pool = get_read_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT 1 FROM plants WHERE tenant_id=$1 AND plant_id=$2",
                    user.tenant_id,
                    plant_id,
                )
                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Plant '{plant_id}' not found in tenant '{user.tenant_id}'",
                    )
    return user
