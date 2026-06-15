"""
routers/departments.py — CRUD endpoints for departments (/departments).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Department, User
from app.schemas import DepartmentCreate, DepartmentUpdate, DepartmentResponse, MessageResponse
from app.auth import get_current_active_user, require_hr_or_admin

router = APIRouter(prefix="/departments", tags=["Departments"])


async def _get_dept_or_404(dept_id: int, db: AsyncSession) -> Department:
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return dept


@router.get("/", response_model=list[DepartmentResponse], summary="List all departments")
async def list_departments(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[Department]:
    result = await db.execute(select(Department).order_by(Department.name))
    return list(result.scalars().all())


@router.get("/{dept_id}", response_model=DepartmentResponse, summary="Get department by ID")
async def get_department(
    dept_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> Department:
    return await _get_dept_or_404(dept_id, db)


@router.post(
    "/",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a department",
    dependencies=[Depends(require_hr_or_admin)],
)
async def create_department(payload: DepartmentCreate, db: AsyncSession = Depends(get_db)) -> Department:
    existing = await db.execute(select(Department).where(Department.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department name already exists")
    dept = Department(**payload.model_dump())
    db.add(dept)
    await db.flush()
    await db.refresh(dept)
    return dept


@router.patch(
    "/{dept_id}",
    response_model=DepartmentResponse,
    summary="Update a department",
    dependencies=[Depends(require_hr_or_admin)],
)
async def update_department(
    dept_id: int,
    payload: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
) -> Department:
    dept = await _get_dept_or_404(dept_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(dept, field, value)
    await db.flush()
    await db.refresh(dept)
    return dept


@router.delete(
    "/{dept_id}",
    response_model=MessageResponse,
    summary="Delete a department",
    dependencies=[Depends(require_hr_or_admin)],
)
async def delete_department(dept_id: int, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    dept = await _get_dept_or_404(dept_id, db)
    await db.delete(dept)
    return MessageResponse(message=f"Department {dept_id} deleted")
