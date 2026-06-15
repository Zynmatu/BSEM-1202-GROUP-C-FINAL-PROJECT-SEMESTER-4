# main.py — FastAPI application entry point
"""
HR Management API
=================
FastAPI + PostgreSQL + SQLAlchemy (async) + JWT OAuth2

Endpoints
---------
/api/v1/auth        — login, register, /me
/api/v1/departments — CRUD
/api/v1/employees   — CRUD + async gather demo
/api/v1/leaves      — CRUD + approval workflow
/api/v1/payroll     — CRUD + async batch processing

Docs
----
/docs   → Swagger UI
/redoc  → ReDoc
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from database import Base, engine
from routers.auth_router import router as auth_router
from routers.department_router import router as dept_router
from routers.employee_router import router as emp_router
from routers.leave_router import router as leave_router
from routers.payroll_router import router as payroll_router

settings = get_settings()


# ── Lifespan: create tables on startup ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Async lifespan context manager.

    On startup  → create all tables (idempotent; use Alembic for migrations).
    On shutdown → dispose the connection pool cleanly.
    """
    async with engine.begin() as conn:
        # Import models so SQLAlchemy knows about them before create_all
        import models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    print("✅  Database tables ready")
    yield
    await engine.dispose()
    print("🛑  Database connection pool closed")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=__doc__,
    contact={"name": "HR API Team", "email": "api@company.com"},
    license_info={"name": "MIT"},
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handlers ─────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "The requested resource was not found"},
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error. Please try again later."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth_router,    prefix=API_PREFIX)
app.include_router(dept_router,    prefix=API_PREFIX)
app.include_router(emp_router,     prefix=API_PREFIX)
app.include_router(leave_router,   prefix=API_PREFIX)
app.include_router(payroll_router, prefix=API_PREFIX)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], summary="Service health check")
async def health_check() -> dict:
    """
    Returns `{"status": "ok"}` when the service is running.

    Can be extended to check DB connectivity, cache, etc.
    """
    return {"status": "ok", "version": settings.app_version}


# ── Root redirect ─────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


# ── Dev entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
