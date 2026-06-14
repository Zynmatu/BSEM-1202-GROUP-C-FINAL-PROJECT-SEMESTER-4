# schemas.py — Pydantic v2 request/response models with full type hints
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from models import (
    EmploymentStatus, LeaveStatus, LeaveType,
    PayrollStatus, UserRole,
)


# ════════════════════════════════════════════════════════════════════════════
# Shared / base helpers
# ════════════════════════════════════════════════════════════════════════════

class OrmBase(BaseModel):
    """All response schemas inherit from this to enable ORM mode."""
    model_config = {"from_attributes": True}


# ════════════════════════════════════════════════════════════════════════════
# Auth / Token
# ════════════════════════════════════════════════════════════════════════════

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int                  # seconds


class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[UserRole] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


# ════════════════════════════════════════════════════════════════════════════
# User
# ════════════════════════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Minimum 8 characters")
    role: UserRole = UserRole.EMPLOYEE

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(OrmBase):
    id: uuid.UUID
    email: EmailStr
    role: UserRole
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime


# ════════════════════════════════════════════════════════════════════════════
# Department
# ════════════════════════════════════════════════════════════════════════════

class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = None
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class DepartmentResponse(OrmBase):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DepartmentDetail(DepartmentResponse):
    employee_count: int = 0          # computed in the route handler


# ════════════════════════════════════════════════════════════════════════════
# Position
# ════════════════════════════════════════════════════════════════════════════

class PositionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    description: Optional[str] = None
    min_salary: Optional[float] = Field(default=None, gt=0)
    max_salary: Optional[float] = Field(default=None, gt=0)
    department_id: int

    @model_validator(mode="after")
    def salary_range_valid(self) -> "PositionCreate":
        if self.min_salary and self.max_salary:
            if self.min_salary > self.max_salary:
                raise ValueError("min_salary must be ≤ max_salary")
        return self


class PositionUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=150)
    description: Optional[str] = None
    min_salary: Optional[float] = Field(default=None, gt=0)
    max_salary: Optional[float] = Field(default=None, gt=0)
    department_id: Optional[int] = None


class PositionResponse(OrmBase):
    id: int
    title: str
    description: Optional[str]
    min_salary: Optional[float]
    max_salary: Optional[float]
    department_id: int
    created_at: datetime


# ════════════════════════════════════════════════════════════════════════════
# Employee
# ════════════════════════════════════════════════════════════════════════════

class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=3, max_length=20, pattern=r"^[A-Z0-9\-]+$")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=20)
    date_of_birth: Optional[date] = None
    hire_date: date
    salary: float = Field(gt=0)
    status: EmploymentStatus = EmploymentStatus.ACTIVE
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    department_id: int
    position_id: int
    user_id: Optional[uuid.UUID] = None
    manager_id: Optional[int] = None


class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    salary: Optional[float] = Field(default=None, gt=0)
    status: Optional[EmploymentStatus] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    department_id: Optional[int] = None
    position_id: Optional[int] = None
    manager_id: Optional[int] = None
    termination_date: Optional[date] = None


class EmployeeResponse(OrmBase):
    id: int
    employee_code: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str]
    date_of_birth: Optional[date]
    hire_date: date
    termination_date: Optional[date]
    salary: float
    status: EmploymentStatus
    address: Optional[str]
    emergency_contact: Optional[str]
    department_id: int
    position_id: int
    user_id: Optional[uuid.UUID]
    manager_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class EmployeeDetail(EmployeeResponse):
    department: Optional[DepartmentResponse] = None
    position: Optional[PositionResponse] = None


# ════════════════════════════════════════════════════════════════════════════
# Leave Request
# ════════════════════════════════════════════════════════════════════════════

class LeaveCreate(BaseModel):
    employee_id: int
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None

    @model_validator(mode="after")
    def date_range_valid(self) -> "LeaveCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class LeaveUpdate(BaseModel):
    status: LeaveStatus
    rejection_reason: Optional[str] = None


class LeaveResponse(OrmBase):
    id: int
    employee_id: int
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str]
    status: LeaveStatus
    approved_by_id: Optional[int]
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]
    created_at: datetime


# ════════════════════════════════════════════════════════════════════════════
# Payroll
# ════════════════════════════════════════════════════════════════════════════

class PayrollCreate(BaseModel):
    employee_id: int
    pay_period_start: date
    pay_period_end: date
    basic_salary: float = Field(gt=0)
    allowances: float = Field(default=0.0, ge=0)
    deductions: float = Field(default=0.0, ge=0)
    tax: float = Field(default=0.0, ge=0)
    payment_date: Optional[date] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def compute_net(self) -> "PayrollCreate":
        # net_salary is always derived — never supplied directly
        return self

    @property
    def net_salary(self) -> float:
        return self.basic_salary + self.allowances - self.deductions - self.tax


class PayrollUpdate(BaseModel):
    allowances: Optional[float] = Field(default=None, ge=0)
    deductions: Optional[float] = Field(default=None, ge=0)
    tax: Optional[float] = Field(default=None, ge=0)
    status: Optional[PayrollStatus] = None
    payment_date: Optional[date] = None
    notes: Optional[str] = None


class PayrollResponse(OrmBase):
    id: int
    employee_id: int
    pay_period_start: date
    pay_period_end: date
    basic_salary: float
    allowances: float
    deductions: float
    tax: float
    net_salary: float
    status: PayrollStatus
    payment_date: Optional[date]
    notes: Optional[str]
    created_at: datetime


# ════════════════════════════════════════════════════════════════════════════
# Generic wrappers
# ════════════════════════════════════════════════════════════════════════════

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list
