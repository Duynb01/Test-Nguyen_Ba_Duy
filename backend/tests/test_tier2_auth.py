import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.core.config import settings
from jose import jwt

def create_expired_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) - timedelta(minutes=10)
    to_encode = {"sub": user_id, "exp": expire, "type": "access", "jti": str(uuid.uuid4())}
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt

@pytest.mark.asyncio
async def test_expired_access_token(client: AsyncClient):
    """Test that an expired JWT token is rejected."""
    token = create_expired_token(str(uuid.uuid4()))
    
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication token"
