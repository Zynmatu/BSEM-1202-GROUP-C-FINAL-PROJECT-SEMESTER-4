"""
routers/leave.py — CRUD endpoints for leave requests (/leave).
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import LeaveRequest, Employee, User, UserRole, LeaveStatus
from app.schemas import LeaveCreate, LeaveUpdate, LeaveResponse, MessageResponse
from app.auth import get_current_active_user, require_hr_or_admin

router = APIRouter(prefix="/leave", tags=["Leave Requests"])


async def _get_leave_or_404(leave_id: int, db: AsyncSession) -> LeaveRequest:
    result = await db.execute(select(LeaveRequest).where(LeaveRequest.id == leave_id))
    leave = result.scalar_one_or_none()
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    return leave


@router.get(
    "/",
    response_model=list[LeaveResponse],
    summary="List leave requests",
)
async def list_leave_requests(
    employee_id: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[LeaveRequest]:
    query = select(LeaveRequest).order_by(LeaveRequest.created_at.desc())
    if employee_id:
        query = query.where(LeaveRequest.employee_id == employee_id)
    if status_filter:
        query = query.where(LeaveRequest.status == status_filter)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{leave_id}", response_model=LeaveResponse, summary="Get a leave request")
async def get_leave_request(
    leave_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> LeaveRequest:
    return await _get_leave_or_404(leave_id, db)


@router.post(
    "/",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a leave request",
)
async def create_leave_request(
    payload: LeaveCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> LeaveRequest:
    emp_result = await db.execute(select(Employee).where(Employee.id == payload.employee_id))
    if not emp_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    leave = LeaveRequest(**payload.model_dump())
    db.add(leave)
    await db.flush()
    await db.refresh(leave)
    return leave


@router.patch(
    "/{leave_id}/review",
    response_model=LeaveResponse,
    summary="Approve or reject a leave request (HR/admin only)",
    dependencies=[Depends(require_hr_or_admin)],
)
async def review_leave_request(
    leave_id: int,
    payload: LeaveUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LeaveRequest:
    leave = await _get_leave_or_404(leave_id, db)
    if leave.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Leave request is already {leave.status.value}",
        )
    if payload.status:
        leave.status = payload.status
    if payload.review_notes:
        leave.review_notes = payload.review_notes
    leave.reviewed_by = current_user.id
    leave.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(leave)
    return leave


@router.patch(
    "/{leave_id}",
    response_model=LeaveResponse,
    summary="Update a leave request (cancel before review)",
)
async def update_leave_request(
    leave_id: int,
    payload: LeaveUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> LeaveRequest:
    leave = await _get_leave_or_404(leave_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(leave, field, value)
    await db.flush()
    await db.refresh(leave)
    return leave


@router.delete(
    "/{leave_id}",
    response_model=MessageResponse,
    summary="Delete a leave request",
    dependencies=[Depends(require_hr_or_admin)],
)
async def delete_leave_request(leave_id: int, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    leave = await _get_leave_or_404(leave_id, db)
    await db.delete(leave)
    return MessageResponse(message=f"Leave request {leave_id} deleted")
