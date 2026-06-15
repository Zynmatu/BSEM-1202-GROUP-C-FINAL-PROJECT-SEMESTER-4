# HR Management API

A production-ready **Human Resource Management REST API** built with:

| Layer | Technology |
|---|---|
| Framework | **FastAPI** (async) |
| Database | **PostgreSQL** via **SQLAlchemy 2** (async) |
| Auth | **OAuth2 + JWT** (python-jose + passlib/bcrypt) |
| Validation | **Pydantic v2** with Python type hints |
| Migrations | **Alembic** (async-aware) |
| Server | **Uvicorn** (ASGI) |

---

## Project Structure

```
hr_api/
├── main.py              # FastAPI app, middleware, router registration
├── config.py            # Pydantic Settings — reads from .env
├── database.py          # Async engine, session factory, get_db dependency
├── models.py            # SQLAlchemy ORM models
├── schemas.py           # Pydantic request/response schemas (type hints)
├── auth.py              # Password hashing, JWT, DI dependencies
├── routers/
│   ├── auth_router.py       # POST /auth/login, /register, GET /auth/me
│   ├── department_router.py # CRUD /departments
│   ├── employee_router.py   # CRUD /employees  ← async/await demo
│   ├── leave_router.py      # CRUD /leaves + approval workflow
│   └── payroll_router.py    # CRUD /payroll + async batch processing
├── alembic/
│   └── env.py           # Async Alembic migration environment
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

## Quick Start

### 1. Clone & enter directory
```bash
git clone <repo>
cd hr_api
```

### 2. Create virtual environment
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env — set DATABASE_URL and SECRET_KEY
```

Generate a secure `SECRET_KEY`:
```bash
openssl rand -hex 32
python -c "import secrets; print(secrets.token_hex(32))
```

### 5. Create PostgreSQL database
```sql
CREATE DATABASE hr_db;
```

### 6. Run database migrations
```bash
alembic upgrade head
```

### 7. Start the server
```bash
python main.py
# or
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 8. Open API docs
| UI | URL |
|---|---| 
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health check | http://localhost:8000/health |

---

## Authentication Flow

```
POST /api/v1/auth/login
  Body: { "email": "admin@company.com", "password": "Secret123" }
  
  → { "access_token": "eyJ...", "token_type": "bearer", "expires_in": 1800 }

# Use token on protected endpoints:
GET /api/v1/employees
  Header: Authorization: Bearer eyJ...
```

---

## API Endpoints

### Auth  `/api/v1/auth`
| Method | Path | Description | Role |
|--------|------|-------------|------|
| `POST` | `/login` | Obtain JWT token | Public |
| `POST` | `/register` | Create user account | Admin |
| `GET` | `/me` | Current user profile | Any |
| `PATCH` | `/me` | Update own profile | Any |
| `GET` | `/users` | List all users | HR/Admin |

### Departments  `/api/v1/departments`
| Method | Path | Description | Role |
|--------|------|-------------|------|
| `GET` | `/` | List departments | Any |
| `GET` | `/{id}` | Department + employee count | Any |
| `POST` | `/` | Create department | HR/Admin |
| `PUT` | `/{id}` | Full replacement | HR/Admin |
| `PATCH` | `/{id}` | Partial update | HR/Admin |
| `DELETE` | `/{id}` | Soft-delete | HR/Admin |

### Employees  `/api/v1/employees`
| Method | Path | Description | Role |
|--------|------|-------------|------|
| `GET` | `/` | List + search + filter | Any |
| `GET` | `/{id}` | Detail w/ dept & position | Any |
| `POST` | `/` | Create employee | HR/Admin |
| `PUT` | `/{id}` | Full replacement | HR/Admin |
| `PATCH` | `/{id}` | Partial update | HR/Admin |
| `DELETE` | `/{id}` | Soft-delete (terminate) | HR/Admin |
| `GET` | `/{id}/direct-reports` | Manager's team | Any |

### Leave Requests  `/api/v1/leaves`
| Method | Path | Description | Role |
|--------|------|-------------|------|
| `GET` | `/` | List (scoped by role) | Any |
| `GET` | `/{id}` | Single request | Any |
| `POST` | `/` | Submit leave | Any |
| `PATCH` | `/{id}` | Approve / reject | HR/Admin |
| `DELETE` | `/{id}` | Cancel pending | Any |

### Payroll  `/api/v1/payroll`
| Method | Path | Description | Role |
|--------|------|-------------|------|
| `GET` | `/` | List records | HR/Admin |
| `GET` | `/{id}` | Single record (own/all) | Any/Admin |
| `POST` | `/` | Create record | HR/Admin |
| `PATCH` | `/{id}` | Update + recompute net | HR/Admin |
| `DELETE` | `/{id}` | Hard delete | Admin |
| `POST` | `/process-batch` | Async batch processing | Admin |

---

## HTTP Status Codes Used

| Code | Meaning |
|------|---------|
| `200 OK` | Successful GET / PATCH |
| `201 Created` | Successful POST |
| `400 Bad Request` | Validation error |
| `401 Unauthorized` | Missing / invalid token |
| `403 Forbidden` | Insufficient role |
| `404 Not Found` | Resource missing |
| `409 Conflict` | Duplicate / state conflict |
| `422 Unprocessable Entity` | Pydantic validation failure |
| `500 Internal Server Error` | Unexpected server fault |

---

## Key Design Decisions

### Async / Await
Every database call uses `await db.execute(...)`. Where multiple independent
queries can run concurrently, `asyncio.gather()` is used — e.g. employee
creation validates department, position, and employee-code uniqueness in
parallel rather than sequentially.

### Dependency Injection (`get_db`)
The `get_db` async generator is injected via `Depends(get_db)` into every
route. It commits on success and rolls back automatically on any exception,
then closes the session — all without any boilerplate in the route handlers.

### Role-Based Access
`require_role(*roles)` is a factory that returns a FastAPI dependency. This
keeps role checks declarative (`dependencies=[Depends(require_admin)]`) rather
than scattered through handler bodies.

### Soft Deletes
Departments set `is_active = False`; Employees set `status = TERMINATED`.
Hard data is never deleted, preserving the audit trail for payroll and leaves.

### Password Security
`passlib[bcrypt]` with `CryptContext(schemes=["bcrypt"])` — industry-standard
adaptive hashing. The `deprecated="auto"` argument enables transparent
hash upgrades.
