"""
auth.py — Authentication & authorisation layer.

Implements:
  • bcrypt password hashing via passlib
  • JWT access + refresh tokens via python-jose
  • OAuth2PasswordBearer DI dependency
  • Role-based access control helpers
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Callable
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User, UserRole
from app.schemas import TokenData

logger = logging.getLogger(__name__)

# ── Password hashing ──────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of the plaintext password."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if the plaintext matches the stored hash."""
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def _create_token(
    data: dict,
    expires_delta: timedelta,
    token_type: str = "access",
) -> str:
    payload = data.copy()
    now = datetime.now(timezone.utc)
    payload.update(
        {
            "iat": now,
            "exp": now + expires_delta,
            "type": token_type,
        }
    )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: int, email: str, role: UserRole) -> str:
    return _create_token(
        {"sub": str(user_id), "email": email, "role": role.value},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        {"sub": str(user_id)},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
    )


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT; raise 401 on any error."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exc
        return TokenData(
            user_id=int(user_id),
            email=payload.get("email"),
            role=UserRole(payload["role"]) if "role" in payload else None,
        )
    except (JWTError, ValueError) as exc:
        logger.warning("JWT decode error: %s", exc)
        raise credentials_exc from exc


# ── FastAPI DI dependencies ───────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the current authenticated user from a Bearer token."""
    token_data = decode_token(token)
    result = await db.execute(select(User).where(User.id == token_data.user_id))
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
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user


# ── Role-based access factories ───────────────────────────────────────────────

def require_roles(*roles: UserRole) -> Callable:
    """
    Return a FastAPI dependency that enforces one of the given roles.

    Usage:
        @router.delete("/employees/{id}", dependencies=[Depends(require_roles(UserRole.ADMIN))])
    """
    async def _check(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {[r.value for r in roles]}",
            )
        return current_user
    return _check


# Convenience aliases
require_admin       = require_roles(UserRole.ADMIN)
require_hr_or_admin = require_roles(UserRole.ADMIN, UserRole.HR_MANAGER)
