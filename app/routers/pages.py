"""
routers/pages.py — HTML page routes + secure /api/users endpoint.
"""
import secrets
from pathlib import Path
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.auth import get_current_active_user, require_hr_or_admin

router = APIRouter(tags=["Pages"])

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


def _read_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"<h1>Template {name} not found</h1>"


@router.get("/dashboard", response_class=HTMLResponse, summary="Main HR Dashboard")
async def dashboard() -> HTMLResponse:
    return HTMLResponse(_read_template("dashboard.html"))


@router.get("/database-viewer", response_class=HTMLResponse, summary="Live Database Viewer")
async def database_viewer() -> HTMLResponse:
    return HTMLResponse(_read_template("database_viewer.html"))


@router.get("/support", response_class=HTMLResponse, summary="Company Support Page")
async def support() -> HTMLResponse:
    return HTMLResponse(_read_template("company_support.html"))


# ── Secure API data endpoint ──────────────────────────────────────────────────

@router.get(
    "/api/users",
    summary="Secure user list for dashboard viewer",
    dependencies=[Depends(require_hr_or_admin)],
)
async def api_users(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """
    Returns a sanitised list of users (no password hashes).
    Used by the Database Viewer frontend page.
    """
    result = await db.execute(
        select(User.id, User.name, User.email, User.role, User.is_active, User.created_at)
        .order_by(User.id)
    )
    rows = result.all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "email": r.email,
            "role": r.role.value,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
