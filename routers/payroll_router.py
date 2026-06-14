# routers/payroll_router.py — payroll CRUD with async processing
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_active_user, require_admin, require_hr_or_admin
from database import get_db
from models import Employee, Payroll, PayrollStatus, User
from schemas import MessageResponse, PayrollCreate, PayrollResponse, PayrollUpdate

router = APIRouter(prefix="/payroll", tags=["Payroll"])


# ── GET /payroll ──────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=list[PayrollResponse],
    summary="List payroll records",
    dependencies=[Depends(require_hr_or_admin)],
)
async def list_payroll(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    employee_id: Optional[int] = Query(default=None),
    pay_status: Optional[PayrollStatus] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> list[Payroll]:
    """List payroll records. **HR Manager / Admin only.**"""
    q = select(Payroll)
    if employee_id:
        q = q.where(Payroll.employee_id == employee_id)
    if pay_status:
        q = q.where(Payroll.status == pay_status)
    result = await db.execute(q.offset(skip).limit(limit))
    return result.scalars().all()


# ── GET /payroll/{id} ─────────────────────────────────────────────────────────

@router.get(
    "/{payroll_id}",
    response_model=PayrollResponse,
    summary="Get a single payroll record",
    responses={404: {"description": "Payroll record not found"}},
)
async def get_payroll(
    payroll_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Payroll:
    """
    Return a payroll record.

    Employees may only see their **own** records; HR/Admin see all.
    """
    record = await _get_or_404(db, payroll_id)

    from models import UserRole
    if current_user.role == UserRole.EMPLOYEE:
        emp_result = await db.execute(
            select(Employee).where(Employee.user_id == current_user.id)
        )
        employee = emp_result.scalar_one_or_none()
        if not employee or record.employee_id != employee.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own payroll records",
            )

    return record


# ── POST /payroll ─────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=PayrollResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a payroll record",
    dependencies=[Depends(require_hr_or_admin)],
)
async def create_payroll(
    payload: PayrollCreate,
    db: AsyncSession = Depends(get_db),
) -> Payroll:
    """
    Create a payroll record for an employee.

    **net_salary** is computed automatically:
    `net = basic_salary + allowances − deductions − tax`

    **HR Manager / Admin only.**
    """
    # Validate employee exists (async)
    emp_result = await db.execute(select(Employee).where(Employee.id == payload.employee_id))
    if not emp_result.scalar_one_or_none():
        raise HTTPException(status_code=422, detail=f"Employee {payload.employee_id} not found")

    net = payload.basic_salary + payload.allowances - payload.deductions - payload.tax

    data = payload.model_dump()
    record = Payroll(**data, net_salary=net)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ── PATCH /payroll/{id} ───────────────────────────────────────────────────────

@router.patch(
    "/{payroll_id}",
    response_model=PayrollResponse,
    summary="Update a payroll record",
    dependencies=[Depends(require_hr_or_admin)],
    responses={404: {"description": "Payroll record not found"}},
)
async def update_payroll(
    payroll_id: int,
    payload: PayrollUpdate,
    db: AsyncSession = Depends(get_db),
) -> Payroll:
    """Partial update of a payroll record. Recomputes net salary if components change."""
    record = await _get_or_404(db, payroll_id)

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(record, field, value)

    # Recompute net salary whenever any component changes
    record.net_salary = record.basic_salary + record.allowances - record.deductions - record.tax

    await db.commit()
    await db.refresh(record)
    return record


# ── DELETE /payroll/{id} ──────────────────────────────────────────────────────

@router.delete(
    "/{payroll_id}",
    response_model=MessageResponse,
    summary="Delete a payroll record",
    dependencies=[Depends(require_admin)],
    responses={404: {"description": "Payroll record not found"}},
)
async def delete_payroll(
    payroll_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Hard-delete a payroll record. **Admin only.**"""
    record = await _get_or_404(db, payroll_id)
    await db.delete(record)
    await db.commit()
    return MessageResponse(message=f"Payroll record #{payroll_id} deleted")


# ── POST /payroll/process-batch ───────────────────────────────────────────────

@router.post(
    "/process-batch",
    response_model=MessageResponse,
    summary="Process all pending payroll records (async batch)",
    dependencies=[Depends(require_admin)],
)
async def process_batch_payroll(
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    **Async batch processing demo** — marks all PENDING payroll records as PROCESSED.

    Uses `asyncio.gather` to simulate concurrent I/O tasks (e.g. writing to an
    external payment gateway) rather than processing them sequentially.
    Each record update is an async await call, demonstrating non-blocking I/O.
    """
    result = await db.execute(
        select(Payroll).where(Payroll.status == PayrollStatus.PENDING)
    )
    pending: list[Payroll] = result.scalars().all()

    if not pending:
        return MessageResponse(message="No pending payroll records found")

    # Simulate concurrent async I/O for each record ──────────────────────────
    async def _process_one(record: Payroll) -> None:
        await asyncio.sleep(0.01)           # simulate payment gateway latency
        record.status = PayrollStatus.PROCESSED

    await asyncio.gather(*(_process_one(r) for r in pending))
    await db.commit()

    return MessageResponse(
        message=f"Batch processing complete",
        detail=f"{len(pending)} payroll records marked as PROCESSED",
    )


# ── Private helpers ───────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, payroll_id: int) -> Payroll:
    result = await db.execute(select(Payroll).where(Payroll.id == payroll_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll record not found")
    return record
