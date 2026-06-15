"""
database.py — Async SQLAlchemy engine, session factory, and DI dependency.

All I/O interactions (queries, inserts, updates) are fully async via asyncpg.
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from app.config import settings


# ── Engine ────────────────────────────────────────────────────────────────────
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,          # Log SQL in dev; silence in prod
    pool_pre_ping=True,           # Recycle stale connections
    pool_size=10,
    max_overflow=20,
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,       # Keep attrs accessible after commit
    autoflush=False,
    autocommit=False,
)


# ── Base model ────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ── Dependency Injection helper ───────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that opens an AsyncSession per request,
    yields it, and guarantees cleanup via finally block.

    Usage:
        @router.get("/items")
        async def read_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Schema initialisation ─────────────────────────────────────────────────────
async def init_db() -> None:
    """Create all tables defined in ORM models (dev/test convenience)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """Drop all tables — use with caution (tests only)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
