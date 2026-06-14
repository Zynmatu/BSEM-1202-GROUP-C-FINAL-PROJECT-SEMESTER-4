# routers/leave_router.py — leave request CRUD + approval workflow
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_active_user, require_hr_or_admin
from database import get_db
from models import Employee, LeaveRequest, LeaveStatus, User
from schemas import LeaveCreate, LeaveResponse, LeaveUpdate, MessageResponse

router = APIRouter(prefix="/leaves", tags=["Leave Requests"])


# ── GET /leaves ───────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=list[LeaveResponse],
    summary="List leave requests",
)
async def list_leaves(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    employee_id: Optional[int] = Query(default=None),
    leave_status: Optional[LeaveStatus] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[LeaveRequest]:
    """
    List leave requests.

    - **Admin / HR Manager**: see all requests.
    - **Employee**: sees only their own requests (enforced via employee record lookup).
    """
    q = select(LeaveRequest)

    # Non-admin users can only see their own leaves
    from models import UserRole
    if current_user.role == UserRole.EMPLOYEE:
        result = await db.execute(
            select(Employee).where(Employee.user_id == current_user.id)
        )
        employee = result.scalar_one_or_none()
        if employee:
            q = q.where(LeaveRequest.employee_id == employee.id)
        else:
            return []

    if employee_id:
        q = q.where(LeaveRequest.employee_id == employee_id)
    if leave_status:
        q = q.where(LeaveRequest.status == leave_status)

    result = await db.execute(q.offset(skip).limit(limit))
    return result.scalars().all()


# ── GET /leaves/{id} ──────────────────────────────────────────────────────────

@router.get(
    "/{leave_id}",
    response_model=LeaveResponse,
    summary="Get a single leave request",
    responses={404: {"description": "Leave request not found"}},
)
async def get_leave(
    leave_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> LeaveRequest:
    return await _get_or_404(db, leave_id)


# ── POST /leaves ──────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a leave request",
)
async def create_leave(
    payload: LeaveCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> LeaveRequest:
    """Submit a new leave request. All authenticated employees may use this endpoint."""
    # Verify employee exists
    emp_result = await db.execute(select(Employee).where(Employee.id == payload.employee_id))
    if not emp_result.scalar_one_or_none():
        raise HTTPException(status_code=422, detail=f"Employee {payload.employee_id} not found")

    leave = LeaveRequest(**payload.model_dump())
    db.add(leave)
    await db.commit()
    await db.refresh(leave)
    return leave


# ── PATCH /leaves/{id} ───────────────────────────────────────────────────────

@router.patch(
    "/{leave_id}",
    response_model=LeaveResponse,
    summary="Approve or reject a leave request",
    dependencies=[Depends(require_hr_or_admin)],
    responses={404: {"description": "Leave request not found"}},
)
async def update_leave_status(
    leave_id: int,
    payload: LeaveUpdate,
    db: AsyncSession = Depends(get_db),
) -> LeaveRequest:
    """
    Approve or reject a leave request.

    - Sets **status** to `approved` or `rejected`.
    - Stamps **approved_at** timestamp when approved.
    - Records **rejection_reason** when rejected.

    **HR Manager / Admin only.**
    """
    leave = await _get_or_404(db, leave_id)

    if leave.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update leave with status '{leave.status.value}'",
        )

    leave.status = payload.status
    if payload.status == LeaveStatus.APPROVED:
        leave.approved_at = datetime.now(timezone.utc)
    elif payload.status == LeaveStatus.REJECTED:
        leave.rejection_reason = payload.rejection_reason

    await db.commit()
    await db.refresh(leave)
    return leave


# ── DELETE /leaves/{id} ───────────────────────────────────────────────────────

@router.delete(
    "/{leave_id}",
    response_model=MessageResponse,
    summary="Cancel / withdraw a leave request",
    responses={404: {"description": "Leave request not found"}},
)
async def cancel_leave(
    leave_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> MessageResponse:
    """Cancel a **pending** leave request. Approved leaves cannot be cancelled via API."""
    leave = await _get_or_404(db, leave_id)

    if leave.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending leave requests can be cancelled",
        )

    await db.delete(leave)
    await db.commit()
    return MessageResponse(message=f"Leave request #{leave_id} cancelled")


# ── Private helpers ───────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, leave_id: int) -> LeaveRequest:
    result = await db.execute(select(LeaveRequest).where(LeaveRequest.id == leave_id))
    leave = result.scalar_one_or_none()
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    return leave
