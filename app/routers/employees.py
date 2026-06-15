"""
routers/employees.py — Full CRUD + async I/O-bound demo (/employees).
"""
import asyncio
import math
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Employee, User, UserRole
from app.schemas import (
    EmployeeCreate, EmployeeUpdate, EmployeeResponse,
    EmployeeListResponse, PaginatedMeta, MessageResponse,
)
from app.auth import get_current_active_user, require_hr_or_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/employees", tags=["Employees"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_emp_number(employee_id: int) -> str:
    return f"EMP-{employee_id:06d}"


async def _get_employee_or_404(employee_id: int, db: AsyncSession) -> Employee:
    result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.department), selectinload(Employee.role))
        .where(Employee.id == employee_id)
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return emp


# ── CRUD Endpoints ────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=EmployeeListResponse,
    summary="List employees with pagination & filters",
)
async def list_employees(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    department_id: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> EmployeeListResponse:
    query = select(Employee).options(
        selectinload(Employee.department),
        selectinload(Employee.role),
    )
    if department_id:
        query = query.where(Employee.department_id == department_id)
    if status:
        query = query.where(Employee.employment_status == status)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    employees = result.scalars().all()

    return EmployeeListResponse(
        data=list(employees),
        meta=PaginatedMeta(total=total, page=page, per_page=per_page, pages=math.ceil(total / per_page) or 1),
    )


@router.get("/{employee_id}", response_model=EmployeeResponse, summary="Get employee by ID")
async def get_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Employee:
    return await _get_employee_or_404(employee_id, db)


@router.post(
    "/",
    response_model=EmployeeResponse,
    status_code=201,
    summary="Create employee profile",
    dependencies=[Depends(require_hr_or_admin)],
)
async def create_employee(
    payload: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
) -> Employee:
    # Verify the user exists
    user_result = await db.execute(select(User).where(User.id == payload.user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # Build a clean dict — treat 0 as "not provided" for FK fields
    data = payload.model_dump(exclude={"employee_number"})
    if not data.get("department_id"):
        data["department_id"] = None
    if not data.get("role_id"):
        data["role_id"] = None

    # Generate a temporary employee number so the NOT NULL constraint is satisfied
    # on the first flush.  We will update it with the real PK-based number next.
    data["employee_number"] = payload.employee_number or "TEMP"

    emp = Employee(**data)
    db.add(emp)
    await db.flush()  # writes the row and gives us emp.id

    # Now we have the real PK — overwrite with the proper number if one was not supplied
    if not payload.employee_number:
        emp.employee_number = _generate_emp_number(emp.id)
        await db.flush()

    await db.refresh(emp)
    return await _get_employee_or_404(emp.id, db)


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Partially update an employee",
    dependencies=[Depends(require_hr_or_admin)],
)
async def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
) -> Employee:
    emp = await _get_employee_or_404(employee_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(emp, field, value)
    await db.flush()
    return await _get_employee_or_404(employee_id, db)


@router.delete(
    "/{employee_id}",
    response_model=MessageResponse,
    summary="Delete employee record (admin only)",
    dependencies=[Depends(require_hr_or_admin)],
)
async def delete_employee(employee_id: int, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    emp = await _get_employee_or_404(employee_id, db)
    await db.delete(emp)
    return MessageResponse(message=f"Employee {employee_id} deleted")


# ── Async I/O-bound demo endpoint ─────────────────────────────────────────────

@router.get(
    "/{employee_id}/enrich",
    summary="[ASYNC DEMO] Enrich employee profile with live public data",
    response_model=dict,
    tags=["Employees", "Async Demo"],
)
async def enrich_employee_profile(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Demonstrates async/await for I/O-bound tasks.

    Concurrently fetches data from two external REST APIs
    (public JSON placeholder APIs) while the employee record
    is read from the database — all in a single asyncio gather call.
    This approach handles multiple I/O operations without blocking
    the event loop.
    """
    emp = await _get_employee_or_404(employee_id, db)

    async def fetch_json(client: httpx.AsyncClient, url: str) -> dict:
        """Async HTTP GET with timeout."""
        try:
            response = await client.get(url, timeout=5.0)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.warning("External API call failed: %s — %s", url, exc)
            return {"error": str(exc)}

    # Fan-out: two external calls run concurrently, not sequentially
    async with httpx.AsyncClient() as client:
        post_task = fetch_json(client, "https://jsonplaceholder.typicode.com/posts/1")
        todo_task = fetch_json(client, "https://jsonplaceholder.typicode.com/todos/1")

        # asyncio.gather runs all coroutines concurrently
        external_post, external_todo = await asyncio.gather(post_task, todo_task)

    return {
        "employee": {
            "id": emp.id,
            "employee_number": emp.employee_number,
            "full_name": emp.full_name,
            "employment_status": emp.employment_status,
        },
        "async_demo": {
            "description": "Two I/O-bound HTTP calls ran concurrently via asyncio.gather",
            "external_post": external_post,
            "external_todo": external_todo,
        },
    }
