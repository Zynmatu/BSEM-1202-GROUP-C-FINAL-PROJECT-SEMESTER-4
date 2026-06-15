# app/routers/__init__.py — re-export all routers for clean imports in main.py
from app.routers import auth, users, employees, departments, roles, payroll, leave, pages

__all__ = ["auth", "users", "employees", "departments", "roles", "payroll", "leave", "pages"]
