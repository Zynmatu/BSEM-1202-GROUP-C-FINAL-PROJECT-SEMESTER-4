# routers/employee_router.py — full CRUD for employees
# Demonstrates async/await for every database I/O-bound operation.
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth import get_current_active_user, require_hr_or_admin
from database import get_db
from models import Department, Employee, Position, User
from schemas import (
    EmployeeCreate, EmployeeDetail,
    EmployeeResponse, EmployeeUpdate, MessageResponse,
)

router = APIRouter(prefix="/employees", tags=["Employees"])


# ── GET /employees ────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=list[EmployeeResponse],
    summary="List employees with optional filters",
)
async def list_employees(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    department_id: Optional[int] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None, description="Search by name or email"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[Employee]:
    """
    Paginated employee list.

    Supports filtering by **department**, **status**, and free-text **search**
    across first name, last name, and email.

    This is an **async I/O-bound** operation: `await db.execute(...)` yields
    control to the event loop while the database query is running, allowing
    other requests to be handled concurrently.
    """
    q = select(Employee)

    if department_id:
        q = q.where(Employee.department_id == department_id)
    if status_filter:
        q = q.where(Employee.status == status_filter)
    if search:
        term = f"%{search.lower()}%"
        from sqlalchemy import or_, func as sql_func
        q = q.where(
            or_(
                sql_func.lower(Employee.first_name).like(term),
                sql_func.lower(Employee.last_name).like(term),
                sql_func.lower(Employee.email).like(term),
            )
        )

    # ── async/await: non-blocking DB call ────────────────────────────────────
    result = await db.execute(q.offset(skip).limit(limit))
    return result.scalars().all()


# ── GET /employees/{id} ───────────────────────────────────────────────────────

@router.get(
    "/{employee_id}",
    response_model=EmployeeDetail,
    summary="Get a single employee with related data",
    responses={404: {"description": "Employee not found"}},
)
async def get_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> Employee:
    """
    Return full employee detail including **department** and **position**.

    Uses `selectinload` to eagerly load relations in a single extra SQL
    statement — avoids N+1 queries while staying async.

    **Async / await demo** — two independent async lookups are executed
    concurrently with `asyncio.gather`:
    """
    # Two async coroutines fired concurrently via asyncio.gather ─────────────
    async def _fetch_employee() -> Employee | None:
        res = await db.execute(
            select(Employee)
            .where(Employee.id == employee_id)
            .options(
                selectinload(Employee.department),
                selectinload(Employee.position),
            )
        )
        return res.scalar_one_or_none()

    async def _fetch_manager_name() -> str | None:
        """Simulate a secondary async lookup (e.g. a separate micro-service)."""
        await asyncio.sleep(0)          # yield to event loop (illustrative)
        return None                     # real impl would query another service

    employee, _ = await asyncio.gather(_fetch_employee(), _fetch_manager_name())
    # ─────────────────────────────────────────────────────────────────────────

    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


# ── POST /employees ───────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new employee record",
    dependencies=[Depends(require_hr_or_admin)],
)
async def create_employee(
    payload: EmployeeCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Employee:
    """
    Create a new employee.  **HR Manager / Admin only.**

    - Validates that `department_id` and `position_id` exist.
    - Validates `employee_code` uniqueness.
    - A **background task** sends the welcome notification asynchronously,
      so the HTTP response is returned immediately without waiting for email/Slack.
    """
    # Parallel existence checks ───────────────────────────────────────────────
    async def _check_dept():
        r = await db.execute(select(Department).where(Department.id == payload.department_id))
        return r.scalar_one_or_none()

    async def _check_pos():
        r = await db.execute(select(Position).where(Position.id == payload.position_id))
        return r.scalar_one_or_none()

    async def _check_code():
        r = await db.execute(select(Employee).where(Employee.employee_code == payload.employee_code))
        return r.scalar_one_or_none()

    dept, pos, existing_code = await asyncio.gather(_check_dept(), _check_pos(), _check_code())

    if not dept:
        raise HTTPException(status_code=422, detail=f"Department {payload.department_id} not found")
    if not pos:
        raise HTTPException(status_code=422, detail=f"Position {payload.position_id} not found")
    if existing_code:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Employee code already in use")

    employee = Employee(**payload.model_dump())
    db.add(employee)
    await db.commit()
    await db.refresh(employee)

    # Fire-and-forget: send welcome e-mail without blocking the response
    background_tasks.add_task(_send_welcome_notification, employee.email, employee.first_name)

    return employee


# ── PUT /employees/{id} ───────────────────────────────────────────────────────

@router.put(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Full employee record replacement",
    dependencies=[Depends(require_hr_or_admin)],
    responses={404: {"description": "Employee not found"}},
)
async def replace_employee(
    employee_id: int,
    payload: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
) -> Employee:
    """Full replacement of an employee record. **HR Manager / Admin only.**"""
    employee = await _get_or_404(db, employee_id)
    for field, value in payload.model_dump().items():
        setattr(employee, field, value)
    await db.commit()
    await db.refresh(employee)
    return employee


# ── PATCH /employees/{id} ─────────────────────────────────────────────────────

@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Partial employee update",
    dependencies=[Depends(require_hr_or_admin)],
    responses={404: {"description": "Employee not found"}},
)
async def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
) -> Employee:
    """Partially update an employee — only supplied fields are changed. **HR Manager / Admin only.**"""
    employee = await _get_or_404(db, employee_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(employee, field, value)
    await db.commit()
    await db.refresh(employee)
    return employee


# ── DELETE /employees/{id} ────────────────────────────────────────────────────

@router.delete(
    "/{employee_id}",
    response_model=MessageResponse,
    summary="Terminate / soft-delete an employee",
    dependencies=[Depends(require_hr_or_admin)],
    responses={404: {"description": "Employee not found"}},
)
async def delete_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Soft-delete: sets **status = TERMINATED** rather than deleting the row.

    Preserves historical payroll and leave records. **HR Manager / Admin only.**
    """
    from models import EmploymentStatus
    employee = await _get_or_404(db, employee_id)
    employee.status = EmploymentStatus.TERMINATED
    await db.commit()
    return MessageResponse(
        message=f"Employee {employee.employee_code} terminated",
        detail="Status set to TERMINATED; record preserved for audit trail",
    )


# ── GET /employees/{id}/direct-reports ───────────────────────────────────────

@router.get(
    "/{employee_id}/direct-reports",
    response_model=list[EmployeeResponse],
    summary="List an employee's direct reports",
)
async def get_direct_reports(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[Employee]:
    """Return all employees whose **manager_id** matches *employee_id*."""
    await _get_or_404(db, employee_id)          # verify manager exists
    result = await db.execute(
        select(Employee).where(Employee.manager_id == employee_id)
    )
    return result.scalars().all()


# ── Private helpers ───────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, employee_id: int) -> Employee:
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


async def _send_welcome_notification(email: str, first_name: str) -> None:
    """
    Simulated async I/O-bound background task.

    In production this would be an async SMTP / Slack / webhook call.
    `asyncio.sleep` here represents the network latency of an email send.
    """
    await asyncio.sleep(0.1)            # simulate network latency
    print(f"[BG TASK] Welcome notification sent to {first_name} <{email}>")
