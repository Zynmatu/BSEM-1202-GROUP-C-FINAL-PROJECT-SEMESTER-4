# routers/auth_router.py — login, register, and /me endpoints
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    create_access_token,
    get_current_active_user,
    hash_password,
    require_admin,
    require_hr_or_admin,
    verify_password,
)
from config import get_settings
from database import get_db
from models import User
from schemas import (
    LoginRequest, MessageResponse, Token,
    UserCreate, UserResponse, UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=Token,
    summary="Obtain a JWT access token",
    responses={401: {"description": "Invalid credentials"}},
)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> Token:
    """
    Authenticate with **email + password** and receive a JWT bearer token.

    Include the token as `Authorization: Bearer <token>` on protected endpoints.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user: User | None = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )

    # Record login timestamp (async I/O-bound write)
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    expire_seconds = settings.access_token_expire_minutes * 60
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value},
        expires_delta=timedelta(seconds=expire_seconds),
    )
    return Token(access_token=token, token_type="bearer", expires_in=expire_seconds)


# ── POST /auth/register ───────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    dependencies=[Depends(require_admin)],   # only admins can create users
)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    """Create a new user account. **Admin only.**"""
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the currently authenticated user",
)
async def me(current_user: User = Depends(get_current_active_user)) -> User:
    """Return profile of the **currently authenticated** user."""
    return current_user


# ── PATCH /auth/me ────────────────────────────────────────────────────────────

@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update own user profile",
)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Update the authenticated user's own profile. Role changes are ignored (use admin endpoint)."""
    if payload.email:
        # Check uniqueness
        existing = await db.execute(select(User).where(User.email == payload.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already in use")
        current_user.email = payload.email

    await db.commit()
    await db.refresh(current_user)
    return current_user


# ── GET /auth/users ───────────────────────────────────────────────────────────

@router.get(
    "/users",
    response_model=list[UserResponse],
    summary="List all user accounts",
    dependencies=[Depends(require_hr_or_admin)],
)
async def list_users(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    """List all registered user accounts. **HR Manager / Admin only.**"""
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()
