"""
schemas.py — Pydantic v2 request / response schemas.

Naming convention:
  <Resource>Base     — shared fields
  <Resource>Create   — POST body
  <Resource>Update   — PATCH body (all optional)
  <Resource>Response — GET / success response
"""
from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator, model_validator, ConfigDict
from app.models import UserRole, EmploymentStatus, LeaveStatus, LeaveType


# ── Generic wrappers ──────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class PaginatedMeta(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int


# ── Auth ──────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenData(BaseModel):
    user_id: int | None = None
    email: str | None = None
    role: UserRole | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── User ──────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: UserRole = UserRole.EMPLOYEE


class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    data: list[UserResponse]
    meta: PaginatedMeta


# ── Department ────────────────────────────────────────────────────────────────

class DepartmentBase(BaseModel):
    name: str
    description: Optional[str] = None
    budget: Optional[float] = None
    is_active: bool = True


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    budget: Optional[float] = None
    is_active: Optional[bool] = None
    manager_id: Optional[int] = None


class DepartmentResponse(DepartmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    manager_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


# ── Role ──────────────────────────────────────────────────────────────────────

class RoleBase(BaseModel):
    title: str
    description: Optional[str] = None
    min_salary: Optional[float] = None
    max_salary: Optional[float] = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    min_salary: Optional[float] = None
    max_salary: Optional[float] = None
    is_active: Optional[bool] = None


class RoleResponse(RoleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


# ── Employee ──────────────────────────────────────────────────────────────────

class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    hire_date: date
    department_id: Optional[int] = None
    role_id: Optional[int] = None
    salary: Optional[float] = None
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE


class EmployeeCreate(EmployeeBase):
    user_id: int
    employee_number: Optional[str] = None  # auto-generated if omitted


class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    department_id: Optional[int] = None
    role_id: Optional[int] = None
    salary: Optional[float] = None
    employment_status: Optional[EmploymentStatus] = None
    termination_date: Optional[date] = None


class EmployeeResponse(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    employee_number: str
    full_name: str
    termination_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    department: Optional[DepartmentResponse] = None
    role: Optional[RoleResponse] = None


class EmployeeListResponse(BaseModel):
    data: list[EmployeeResponse]
    meta: PaginatedMeta


# ── Payroll ───────────────────────────────────────────────────────────────────

class PayrollBase(BaseModel):
    pay_period_start: date
    pay_period_end: date
    base_salary: float
    bonuses: float = 0.0
    deductions: float = 0.0
    payment_date: Optional[date] = None
    notes: Optional[str] = None


class PayrollCreate(PayrollBase):
    employee_id: int

    @model_validator(mode="after")
    def compute_net(self) -> "PayrollCreate":
        object.__setattr__(
            self, "net_pay", self.base_salary + self.bonuses - self.deductions
        )
        return self

    net_pay: float = 0.0


class PayrollUpdate(BaseModel):
    bonuses: Optional[float] = None
    deductions: Optional[float] = None
    payment_date: Optional[date] = None
    notes: Optional[str] = None


class PayrollResponse(PayrollBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    net_pay: float
    created_at: datetime


# ── Leave ─────────────────────────────────────────────────────────────────────

class LeaveBase(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveCreate(LeaveBase):
    employee_id: int

    @model_validator(mode="after")
    def compute_days(self) -> "LeaveCreate":
        delta = (self.end_date - self.start_date).days + 1
        if delta <= 0:
            raise ValueError("end_date must be after start_date")
        object.__setattr__(self, "days_requested", delta)
        return self

    days_requested: int = 0


class LeaveUpdate(BaseModel):
    status: Optional[LeaveStatus] = None
    review_notes: Optional[str] = None


class LeaveResponse(LeaveBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    days_requested: int
    status: LeaveStatus
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
