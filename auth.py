# auth.py — password hashing, JWT creation/verification, FastAPI dependencies
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models import User, UserRole
from schemas import TokenData

settings = get_settings()

# ── Password hashing ──────────────────────────────────────────────────────────
# bcrypt is the industry standard; schemes list allows future migration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return the bcrypt hash of *plain*."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Encode *data* into a signed JWT with an expiry claim."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    to_encode["iat"] = datetime.now(timezone.utc)
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT; raise 401 on any error."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: Optional[str] = payload.get("sub")
        role_str: Optional[str] = payload.get("role")
        if user_id is None:
            raise credentials_exc
        return TokenData(user_id=user_id, role=UserRole(role_str) if role_str else None)
    except JWTError:
        raise credentials_exc


# ── FastAPI dependencies ──────────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the bearer token to the matching User row (async DB lookup)."""
    token_data = decode_token(token)

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(token_data.user_id))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Thin wrapper — raises 400 if the account is disabled."""
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


# ── Role-based access helpers ─────────────────────────────────────────────────

def require_role(*roles: UserRole):
    """
    Factory that returns a FastAPI dependency enforcing one of *roles*.

    Usage::

        @router.get("/admin-only")
        async def admin_endpoint(user = Depends(require_role(UserRole.ADMIN))):
            ...
    """
    async def _check(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in roles]}",
            )
        return current_user
    return _check


# Convenience aliases
require_admin = require_role(UserRole.ADMIN)
require_hr_or_admin = require_role(UserRole.ADMIN, UserRole.HR_MANAGER)
