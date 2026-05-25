from fastapi.testclient import TestClient

from app.identity.auth import Permission, get_current_user
from app.main import app
from app.models import UserContext


def override_require_permission_admin():
    async def _override():
        return UserContext(
            user_id="1",
            tenant_id="piccadily",
            email="admin@piccadily.com",
            role="admin",
            is_edge=False,
            permissions=[Permission.ADMIN_FULL],
        )

    return _override


def override_require_permission_viewer():
    async def _override():
        return UserContext(
            user_id="2",
            tenant_id="piccadily",
            email="viewer@piccadily.com",
            role="viewer",
            is_edge=False,
            permissions=[Permission.METADATA_READ],
            plant_ids=["BOILER_PLC_01"],
        )

    return _override


def override_require_plant_access_success():
    async def _override():
        pass

    return _override


def override_require_plant_access_fail():
    from fastapi import HTTPException

    async def _override():
        raise HTTPException(status_code=403, detail="Access denied to plant")

    return _override


def test_admin_access_allowed(client: TestClient, mock_db_conn):
    app.dependency_overrides[get_current_user] = override_require_permission_admin()
    from app.infra.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db_conn

    resp = client.post("/api/v1/admin/tenants", json={"name": "Test Tenant"})
    assert resp.status_code in (200, 201)

    app.dependency_overrides.clear()


def test_admin_access_denied_for_viewer(client: TestClient, mock_db_conn):
    app.dependency_overrides[get_current_user] = override_require_permission_viewer()
    from app.infra.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db_conn

    resp = client.post("/api/v1/admin/tenants", json={"name": "Test Tenant 2"})
    assert resp.status_code == 403

    app.dependency_overrides.clear()


def test_plant_access_enforcement(client: TestClient, mock_db_conn):
    app.dependency_overrides[get_current_user] = override_require_permission_viewer()
    from app.infra.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db_conn

    resp = client.get("/api/v1/tags?plant_id=WTP_NODE_01")
    assert resp.status_code == 403

    app.dependency_overrides.clear()


def test_plant_access_allowed(client: TestClient, mock_db_conn):
    app.dependency_overrides[get_current_user] = override_require_permission_viewer()
    from app.infra.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db_conn

    resp = client.get("/api/v1/tags?plant_id=BOILER_PLC_01")
    assert resp.status_code == 200

    app.dependency_overrides.clear()
