import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.db.session import get_db
from app.models.user import User
from app.schemas.todo import TodoCreate, TodoListResponse, TodoResponse, TodoUpdate
from app.services.todo_service import (
    create_todo,
    delete_todo,
    get_todo_by_id,
    get_todos,
    update_todo,
)

router = APIRouter()

CACHE_TTL = 300  # 5 minutes


async def _list_cache_key(
    redis: RedisClient, user_id: uuid.UUID, page: int, size: int
) -> str:
    version = await redis.get(f"todos:ver:{user_id}") or "0"
    return f"todos:list:{user_id}:{version}:{page}:{size}"


async def _invalidate_user_cache(redis: RedisClient, user_id: uuid.UUID) -> None:
    # Bump the per-user version; old list entries become unreachable and expire by TTL
    await redis.set(f"todos:ver:{user_id}", uuid.uuid4().hex)


async def _get_owned_todo(db: AsyncSession, todo_id: uuid.UUID, user: User):
    todo = await get_todo_by_id(db, todo_id)
    # Return 404 (not 403) to avoid leaking the existence of other users' todos
    if not todo or todo.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    return todo


@router.get("", response_model=TodoListResponse)
async def list_todos(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Get paginated list of todos."""
    skip = (page - 1) * size

    cache_key = await _list_cache_key(redis, current_user.id, page, size)

    # Try to get from cache
    cached = await redis.get(cache_key)
    if cached:
        cached_data = json.loads(cached)
        return TodoListResponse(**cached_data)

    todos, total = await get_todos(db, user_id=current_user.id, skip=skip, limit=size)

    items = [
        TodoResponse(
            id=todo.id,
            title=todo.title,
            description=todo.description,
            completed=todo.completed,
            user_id=todo.user_id,
            created_at=todo.created_at,
            updated_at=todo.updated_at,
            user_email=current_user.email,
        )
        for todo in todos
    ]

    response = TodoListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )

    # Cache the response
    await redis.set(cache_key, response.model_dump_json(), ex=CACHE_TTL)

    return response


@router.post("", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_new_todo(
    todo_data: TodoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Create a new todo item."""
    todo = await create_todo(db, todo_data, current_user.id)
    await _invalidate_user_cache(redis, current_user.id)
    return todo


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific todo by ID."""
    return await _get_owned_todo(db, todo_id, current_user)


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_existing_todo(
    todo_id: uuid.UUID,
    todo_data: TodoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Update a todo item."""
    todo = await _get_owned_todo(db, todo_id, current_user)

    # Only apply fields the client actually sent (keeps completed=False and
    # does not erase description on partial updates)
    update_data = todo_data.model_dump(exclude_unset=True)
    if update_data.get("title") is None:
        update_data.pop("title", None)
    if update_data.get("completed") is None:
        update_data.pop("completed", None)

    updated_todo = await update_todo(db, todo, update_data)
    await _invalidate_user_cache(redis, current_user.id)

    return updated_todo


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Delete a todo item."""
    todo = await _get_owned_todo(db, todo_id, current_user)

    await delete_todo(db, todo)
    await _invalidate_user_cache(redis, current_user.id)

    return None
