# database.py — async SQLAlchemy engine + session factory + DI dependency
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

settings = get_settings()

# ── Engine ───────────────────────────────────────────────────────────────────
# pool_pre_ping=True: test connections before handing them out (avoids stale)
# echo=settings.debug: logs SQL when DEBUG=True — turn off in production
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
)

# ── Session factory ──────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,   # attributes stay accessible after commit
    autoflush=False,
    autocommit=False,
)


# ── Declarative base ─────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """All ORM models inherit from this base."""
    pass


# ── Dependency: get_db ───────────────────────────────────────────────────────
# Injected via FastAPI's Depends(get_db).
# The session is automatically closed (and rolled back on error) when the
# request finishes — even if an exception is raised mid-route.
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
