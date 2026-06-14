# routers/department_router.py — full CRUD for departments
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_active_user, require_hr_or_admin
from database import get_db
from models import Department, Employee, User
from schemas import (
    DepartmentCreate, DepartmentDetail,
    DepartmentResponse, DepartmentUpdate, MessageResponse,
)

router = APIRouter(prefix="/departments", tags=["Departments"])


# ── GET /departments ──────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=list[DepartmentResponse],
    summary="List all departments",
)
async def list_departments(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[Department]:
    """Retrieve a paginated list of departments."""
    q = select(Department)
    if active_only:
        q = q.where(Department.is_active.is_(True))
    result = await db.execute(q.offset(skip).limit(limit))
    return result.scalars().all()


# ── GET /departments/{id} ─────────────────────────────────────────────────────

@router.get(
    "/{department_id}",
    response_model=DepartmentDetail,
    summary="Get a single department",
    responses={404: {"description": "Department not found"}},
)
async def get_department(
    department_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> DepartmentDetail:
    """Return full details for a department, including the employee count."""
    dept = await _get_or_404(db, department_id)

    count_result = await db.execute(
        select(func.count(Employee.id)).where(Employee.department_id == department_id)
    )
    employee_count = count_result.scalar_one()

    detail = DepartmentDetail.model_validate(dept)
    detail.employee_count = employee_count
    return detail


# ── POST /departments ─────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a department",
    dependencies=[Depends(require_hr_or_admin)],
)
async def create_department(
    payload: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
) -> Department:
    """Create a new department. **HR Manager / Admin only.**"""
    # Uniqueness check
    existing = await db.execute(select(Department).where(Department.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department name already exists")

    dept = Department(**payload.model_dump())
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    return dept


# ── PUT /departments/{id} ─────────────────────────────────────────────────────

@router.put(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Replace a department (full update)",
    dependencies=[Depends(require_hr_or_admin)],
    responses={404: {"description": "Department not found"}},
)
async def replace_department(
    department_id: int,
    payload: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
) -> Department:
    """Full replacement of a department record. **HR Manager / Admin only.**"""
    dept = await _get_or_404(db, department_id)
    for field, value in payload.model_dump().items():
        setattr(dept, field, value)
    await db.commit()
    await db.refresh(dept)
    return dept


# ── PATCH /departments/{id} ───────────────────────────────────────────────────

@router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Partial update a department",
    dependencies=[Depends(require_hr_or_admin)],
    responses={404: {"description": "Department not found"}},
)
async def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
) -> Department:
    """Partially update a department — only supplied fields are changed."""
    dept = await _get_or_404(db, department_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(dept, field, value)
    await db.commit()
    await db.refresh(dept)
    return dept


# ── DELETE /departments/{id} ──────────────────────────────────────────────────

@router.delete(
    "/{department_id}",
    response_model=MessageResponse,
    summary="Soft-delete a department",
    dependencies=[Depends(require_hr_or_admin)],
    responses={404: {"description": "Department not found"}},
)
async def delete_department(
    department_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Soft-delete: sets **is_active = False** rather than destroying the row.

    This preserves historical employee references. **HR Manager / Admin only.**
    """
    dept = await _get_or_404(db, department_id)
    dept.is_active = False
    await db.commit()
    return MessageResponse(message=f"Department '{dept.name}' deactivated successfully")


# ── Private helpers ───────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, department_id: int) -> Department:
    result = await db.execute(select(Department).where(Department.id == department_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return dept
