import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock
from app.api.deps import get_redis

async def get_auth_token(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return response.json()["access_token"]

@pytest.mark.asyncio
async def test_cross_user_isolation(client: AsyncClient):
    """Test that User A cannot read, update, or delete User B's todos."""
    token_a = await get_auth_token(client, "userA@example.com")
    token_b = await get_auth_token(client, "userB@example.com")
    
    # User A creates a todo
    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "User A Todo"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    todo_id = create_resp.json()["id"]
    
    # User B tries to read User A's todo
    read_resp = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert read_resp.status_code == 404
    
    # User B tries to update User A's todo
    update_resp = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Hacked by User B"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert update_resp.status_code == 404
    
    # User B tries to delete User A's todo
    delete_resp = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert delete_resp.status_code == 404

@pytest.mark.asyncio
async def test_toggle_completed_to_false(client: AsyncClient):
    """Test that completed can be toggled from true back to false."""
    token = await get_auth_token(client, "toggle@example.com")
    
    # Create
    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "Toggle me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_resp.json()["id"]
    
    # Set to true
    update_resp = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"completed": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_resp.json()["completed"] is True
    
    # Set back to false
    update_resp2 = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"completed": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_resp2.json()["completed"] is False

@pytest.mark.asyncio
async def test_partial_update_keeps_description(client: AsyncClient):
    """Test that updating title does not erase description."""
    token = await get_auth_token(client, "partial@example.com")
    
    # Create with description
    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "Original Title", "description": "Original Desc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_resp.json()["id"]
    
    # Partial update title only
    update_resp = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "New Title"},
        headers={"Authorization": f"Bearer {token}"},
    )
    
    data = update_resp.json()
    assert data["title"] == "New Title"
    assert data["description"] == "Original Desc"

@pytest.mark.asyncio
async def test_cache_invalidation_on_mutations(client: AsyncClient):
    """Test that creating, updating, or deleting a todo updates the cache version."""
    from app.main import app
    from unittest.mock import MagicMock, AsyncMock
    
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()
    
    app.dependency_overrides[get_redis] = lambda: mock_redis
    
    token = await get_auth_token(client, "cache@example.com")
    
    # Reset mock counters (registering can use redis, so we reset)
    mock_redis.set.reset_mock()
    
    # Create
    create_resp = await client.post(
        "/api/v1/todos",
        json={"title": "Cache me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_resp.json()["id"]
    
    set_calls = mock_redis.set.call_args_list
    assert any("todos:ver" in args[0][0] for args in set_calls), "Cache version not updated on create"
    
    mock_redis.set.reset_mock()
    
    # Update
    await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Updated Cache"},
        headers={"Authorization": f"Bearer {token}"},
    )
    set_calls = mock_redis.set.call_args_list
    assert any("todos:ver" in args[0][0] for args in set_calls), "Cache version not updated on update"
    
    mock_redis.set.reset_mock()
    
    # Delete
    await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    set_calls = mock_redis.set.call_args_list
    assert any("todos:ver" in args[0][0] for args in set_calls), "Cache version not updated on delete"
    
    # Cleanup overrides
    app.dependency_overrides.pop(get_redis, None)
