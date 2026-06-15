"""
seed.py — Populate the HR database with realistic demo data.

Run with: python seed.py
"""
import asyncio
from datetime import date, timedelta
from app.database import AsyncSessionLocal, init_db
from app.models import User, Employee, Department, Role, PayrollRecord, LeaveRequest, UserRole, EmploymentStatus, LeaveType, LeaveStatus
from app.auth import hash_password


DEPARTMENTS = [
    {"name": "Engineering",      "description": "Product development and infrastructure",  "budget": 500000},
    {"name": "Human Resources",  "description": "People ops, recruitment, and culture",     "budget": 200000},
    {"name": "Finance",          "description": "Accounting, payroll, and financial planning","budget": 150000},
    {"name": "Sales",            "description": "Revenue and business development",          "budget": 300000},
    {"name": "Operations",       "description": "Facilities, IT, and logistics",             "budget": 180000},
]

ROLES = [
    {"title": "Software Engineer",        "min_salary": 60000,  "max_salary": 120000},
    {"title": "Senior Software Engineer", "min_salary": 90000,  "max_salary": 160000},
    {"title": "HR Manager",               "min_salary": 55000,  "max_salary": 95000},
    {"title": "Payroll Specialist",        "min_salary": 45000,  "max_salary": 75000},
    {"title": "Sales Executive",           "min_salary": 40000,  "max_salary": 80000},
    {"title": "Operations Manager",        "min_salary": 60000,  "max_salary": 100000},
]

USERS = [
    {"name": "Alice Johnson",  "email": "alice@apexcorp.com",   "password": "Admin@1234",   "role": UserRole.ADMIN},
    {"name": "Bob Martinez",   "email": "bob@apexcorp.com",     "password": "HrPass@1234",  "role": UserRole.HR_MANAGER},
    {"name": "Carol White",    "email": "carol@apexcorp.com",   "password": "Emp@123456",   "role": UserRole.EMPLOYEE},
    {"name": "David Kim",      "email": "david@apexcorp.com",   "password": "Emp@123456",   "role": UserRole.EMPLOYEE},
    {"name": "Eva Chen",       "email": "eva@apexcorp.com",     "password": "Read@12345",   "role": UserRole.READONLY},
]


async def seed():
    print("⏳  Initialising database schema…")
    await init_db()

    async with AsyncSessionLocal() as db:
        # Departments
        print("🏢  Seeding departments…")
        depts = []
        for d in DEPARTMENTS:
            dept = Department(**d)
            db.add(dept)
            depts.append(dept)
        await db.flush()

        # Roles
        print("💼  Seeding job roles…")
        roles = []
        for r in ROLES:
            role = Role(**r)
            db.add(role)
            roles.append(role)
        await db.flush()

        # Users + Employees
        print("👤  Seeding users and employees…")
        for i, u in enumerate(USERS):
            user = User(
                name=u["name"],
                email=u["email"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
            )
            db.add(user)
            await db.flush()

            dept  = depts[i % len(depts)]
            jrole = roles[i % len(roles)]
            emp = Employee(
                user_id=user.id,
                employee_number=f"EMP-{user.id:06d}",
                first_name=u["name"].split()[0],
                last_name=u["name"].split()[-1],
                hire_date=date.today() - timedelta(days=365 * (i + 1)),
                department_id=dept.id,
                role_id=jrole.id,
                salary=(jrole.min_salary + jrole.max_salary) / 2,
                employment_status=EmploymentStatus.ACTIVE,
            )
            db.add(emp)
            await db.flush()

            # Payroll record
            pr = PayrollRecord(
                employee_id=emp.id,
                pay_period_start=date(date.today().year, date.today().month, 1),
                pay_period_end=date.today(),
                base_salary=emp.salary,
                bonuses=1000 if i == 0 else 0,
                deductions=500,
                net_pay=emp.salary + (1000 if i == 0 else 0) - 500,
                payment_date=date.today(),
            )
            db.add(pr)

            # Leave request for some employees
            if i in (2, 3):
                lr = LeaveRequest(
                    employee_id=emp.id,
                    leave_type=LeaveType.ANNUAL,
                    start_date=date.today() + timedelta(days=7),
                    end_date=date.today() + timedelta(days=14),
                    days_requested=8,
                    reason="Annual family vacation",
                    status=LeaveStatus.PENDING,
                )
                db.add(lr)

        await db.commit()
        print("✅  Seed complete! Users created:")
        for u in USERS:
            print(f"   {u['email']:30s}  password: {u['password']:15s}  role: {u['role'].value}")


if __name__ == "__main__":
    asyncio.run(seed())
