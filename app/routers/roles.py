"""
routers/roles.py — CRUD endpoints for job roles (/roles).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Role, User
from app.schemas import RoleCreate, RoleUpdate, RoleResponse, MessageResponse
from app.auth import get_current_active_user, require_hr_or_admin

router = APIRouter(prefix="/roles", tags=["Roles"])


async def _get_role_or_404(role_id: int, db: AsyncSession) -> Role:
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.get("/", response_model=list[RoleResponse], summary="List all job roles")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[Role]:
    result = await db.execute(select(Role).order_by(Role.title))
    return list(result.scalars().all())


@router.get("/{role_id}", response_model=RoleResponse, summary="Get role by ID")
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> Role:
    return await _get_role_or_404(role_id, db)


@router.post(
    "/",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a job role",
    dependencies=[Depends(require_hr_or_admin)],
)
async def create_role(payload: RoleCreate, db: AsyncSession = Depends(get_db)) -> Role:
    existing = await db.execute(select(Role).where(Role.title == payload.title))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role title already exists")
    role = Role(**payload.model_dump())
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return role


@router.patch(
    "/{role_id}",
    response_model=RoleResponse,
    summary="Update a job role",
    dependencies=[Depends(require_hr_or_admin)],
)
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: AsyncSession = Depends(get_db),
) -> Role:
    role = await _get_role_or_404(role_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, field, value)
    await db.flush()
    await db.refresh(role)
    return role


@router.delete(
    "/{role_id}",
    response_model=MessageResponse,
    summary="Delete a job role",
    dependencies=[Depends(require_hr_or_admin)],
)
async def delete_role(role_id: int, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    role = await _get_role_or_404(role_id, db)
    await db.delete(role)
    return MessageResponse(message=f"Role {role_id} deleted")
