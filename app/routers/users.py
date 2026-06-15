"""
routers/users.py — CRUD endpoints for system users (/users).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, UserRole
from app.schemas import UserCreate, UserUpdate, UserResponse, UserListResponse, PaginatedMeta, MessageResponse
from app.auth import hash_password, get_current_active_user, require_admin, require_hr_or_admin
import math

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/",
    response_model=UserListResponse,
    summary="List all users (admin / HR only)",
    dependencies=[Depends(require_hr_or_admin)],
)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    query = select(User)
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    users = result.scalars().all()

    return UserListResponse(
        data=list(users),
        meta=PaginatedMeta(total=total, page=page, per_page=per_page, pages=math.ceil(total / per_page) or 1),
    )


@router.get("/{user_id}", response_model=UserResponse, summary="Fetch a user by ID")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> User:
    # Users can view their own profile; admins/HR can view anyone
    if current_user.id != user_id and current_user.role not in (UserRole.ADMIN, UserRole.HR_MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user (admin only)",
    dependencies=[Depends(require_admin)],
)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Partially update a user",
)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.id != user_id and current_user.role not in (UserRole.ADMIN, UserRole.HR_MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))
    # Non-admins cannot escalate their own role
    if "role" in update_data and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins may change roles")

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return user


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Delete a user (admin only)",
    dependencies=[Depends(require_admin)],
)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.delete(user)
    return MessageResponse(message=f"User {user_id} deleted successfully")
