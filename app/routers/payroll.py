"""
routers/payroll.py — CRUD endpoints for payroll records (/payroll).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import PayrollRecord, Employee, User
from app.schemas import PayrollCreate, PayrollUpdate, PayrollResponse, MessageResponse
from app.auth import get_current_active_user, require_hr_or_admin

router = APIRouter(prefix="/payroll", tags=["Payroll"])


async def _get_record_or_404(record_id: int, db: AsyncSession) -> PayrollRecord:
    result = await db.execute(select(PayrollRecord).where(PayrollRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll record not found")
    return record


@router.get(
    "/",
    response_model=list[PayrollResponse],
    summary="List payroll records (filter by employee)",
    dependencies=[Depends(require_hr_or_admin)],
)
async def list_payroll(
    employee_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[PayrollRecord]:
    query = select(PayrollRecord).order_by(PayrollRecord.pay_period_start.desc())
    if employee_id:
        query = query.where(PayrollRecord.employee_id == employee_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get(
    "/{record_id}",
    response_model=PayrollResponse,
    summary="Get a payroll record",
)
async def get_payroll_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> PayrollRecord:
    return await _get_record_or_404(record_id, db)


@router.post(
    "/",
    response_model=PayrollResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create payroll record",
    dependencies=[Depends(require_hr_or_admin)],
)
async def create_payroll(payload: PayrollCreate, db: AsyncSession = Depends(get_db)) -> PayrollRecord:
    # Verify employee exists
    emp_result = await db.execute(select(Employee).where(Employee.id == payload.employee_id))
    if not emp_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    net_pay = payload.base_salary + payload.bonuses - payload.deductions
    record = PayrollRecord(
        **payload.model_dump(exclude={"net_pay"}),
        net_pay=net_pay,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


@router.patch(
    "/{record_id}",
    response_model=PayrollResponse,
    summary="Update a payroll record",
    dependencies=[Depends(require_hr_or_admin)],
)
async def update_payroll(
    record_id: int,
    payload: PayrollUpdate,
    db: AsyncSession = Depends(get_db),
) -> PayrollRecord:
    record = await _get_record_or_404(record_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    # Recalculate net pay if financials changed
    record.net_pay = record.base_salary + record.bonuses - record.deductions
    await db.flush()
    await db.refresh(record)
    return record


@router.delete(
    "/{record_id}",
    response_model=MessageResponse,
    summary="Delete a payroll record",
    dependencies=[Depends(require_hr_or_admin)],
)
async def delete_payroll(record_id: int, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    record = await _get_record_or_404(record_id, db)
    await db.delete(record)
    return MessageResponse(message=f"Payroll record {record_id} deleted")
