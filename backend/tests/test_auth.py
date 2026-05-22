"""
Piccadily Industrial Historian — Authentication Module Tests
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from app.identity.auth import get_current_user


@pytest.mark.asyncio
async def test_get_current_user_invalid_jwt():
    request = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await get_current_user(request, authorization="Bearer invalid_token")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_valid_api_key():
    request = AsyncMock()

    with patch("app.identity.auth._verify_edge_api_key_db", return_value="piccadily") as mock_verify:
        user = await get_current_user(request, x_api_key="valid_raw_key")
        assert user.is_edge is True
        assert user.tenant_id == "piccadily"
        assert user.role == "edge_agent"
        mock_verify.assert_called_once_with("valid_raw_key")
