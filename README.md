# 🏢 HR Management API

A production-ready **Human Resource Management REST API** built with:

| Stack | Choice |
|---|---|
| Framework | FastAPI (async) |
| Database | PostgreSQL + SQLAlchemy 2 (async) |
| Auth | OAuth2 Password Flow + JWT (access + refresh) |
| Password | bcrypt via passlib |
| Validation | Pydantic v2 |
| Migrations | Alembic |
| Driver | asyncpg |

---

## 📂 Project Structure

```
hr_api/
├── main.py                    # App factory, routes, custom docs UI
├── seed.py                    # Demo data seeder
├── alembic_setup.py           # Alembic scaffold helper
├── requirements.txt
├── .env.example               # Copy to .env and fill in
│
├── app/
│   ├── config.py              # Pydantic settings (loads .env)
│   ├── database.py            # Async engine, session factory, get_db DI
│   ├── models.py              # SQLAlchemy ORM models
│   ├── schemas.py             # Pydantic v2 request/response schemas
│   ├── auth.py                # JWT helpers, password hashing, role guards
│   └── routers/
│       ├── auth.py            # /auth — register, login, refresh, me
│       ├── users.py           # /users — CRUD
│       ├── employees.py       # /employees — CRUD + async enrichment demo
│       ├── departments.py     # /departments — CRUD
│       ├── roles.py           # /roles — CRUD
│       ├── payroll.py         # /payroll — CRUD
│       ├── leave.py           # /leave — CRUD + review workflow
│       └── pages.py           # /dashboard, /database-viewer, /support, /api/users
│
├── templates/
│   ├── dashboard.html         # Main dashboard with sidebar + embedded docs
│   ├── database_viewer.html   # Live database table viewer
│   └── company_support.html   # About, contact, FAQ
│
└── static/
    └── favicon.svg
```

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 14+

### 2. Install dependencies

```bash
cd hr_api
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL and generate a SECRET_KEY:
python -c "import secrets; print(secrets.token_hex(64))"
```

### 4. Start the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The app calls `init_db()` on startup which auto-creates all tables.

### 5. (Optional) Seed demo data

```bash
python seed.py
```

---

## 🔗 Endpoints at a glance

| URL | Description |
|---|---|
| `/` | → redirects to `/dashboard` |
| `/dashboard` | Management dashboard (HTML) |
| `/database-viewer` | Live database viewer (HTML) |
| `/support` | Company support page (HTML) |
| `/docs` | Custom Swagger UI |
| `/redoc` | Branded ReDoc |
| `/docs/hr` | Alias for `/redoc` |
| `/openapi.json` | Raw OpenAPI schema |
| `/health` | Health check JSON |
| `/api/users` | Secure user list for dashboard |

### API Modules

```
POST   /auth/register
POST   /auth/token         ← OAuth2 form
POST   /auth/login         ← JSON body
POST   /auth/refresh
GET    /auth/me

GET    /users/             (admin/HR)
GET    /users/{id}
POST   /users/             (admin)
PATCH  /users/{id}
DELETE /users/{id}         (admin)

GET    /employees/
GET    /employees/{id}
POST   /employees/         (admin/HR)
PATCH  /employees/{id}     (admin/HR)
DELETE /employees/{id}     (admin/HR)
GET    /employees/{id}/enrich   ← async I/O demo

GET    /departments/
GET    /departments/{id}
POST   /departments/       (admin/HR)
PATCH  /departments/{id}   (admin/HR)
DELETE /departments/{id}   (admin/HR)

GET    /roles/
GET    /roles/{id}
POST   /roles/             (admin/HR)
PATCH  /roles/{id}         (admin/HR)
DELETE /roles/{id}         (admin/HR)

GET    /payroll/           (admin/HR)
GET    /payroll/{id}
POST   /payroll/           (admin/HR)
PATCH  /payroll/{id}       (admin/HR)
DELETE /payroll/{id}       (admin/HR)

GET    /leave/
GET    /leave/{id}
POST   /leave/
PATCH  /leave/{id}
PATCH  /leave/{id}/review  (admin/HR)
DELETE /leave/{id}         (admin/HR)
```

---

## 🔐 Authentication

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Jane Doe","email":"jane@example.com","password":"Secret@123","role":"admin"}'

# Login (JSON)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"jane@example.com","password":"Secret@123"}'

# Login (OAuth2 form — for Swagger UI)
curl -X POST http://localhost:8000/auth/token \
  -F "username=jane@example.com" \
  -F "password=Secret@123"

# Use token
curl http://localhost:8000/employees/ \
  -H "Authorization: Bearer <access_token>"
```

---

## ⚡ Async Demo

`GET /employees/{id}/enrich` demonstrates concurrent I/O:

```python
# Two external HTTP calls run concurrently via asyncio.gather
post_task = fetch_json(client, "https://jsonplaceholder.typicode.com/posts/1")
todo_task = fetch_json(client, "https://jsonplaceholder.typicode.com/todos/1")
external_post, external_todo = await asyncio.gather(post_task, todo_task)
```

This halves latency vs sequential `await` calls when fetching from multiple sources.

---

## 🗄️ Database Migrations (Production)

```bash
python alembic_setup.py          # Scaffold Alembic once
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

---

## 👥 Demo Users (after seeding)

| Email | Password | Role |
|---|---|---|
| alice@apexcorp.com | Admin@1234 | admin |
| bob@apexcorp.com | HrPass@1234 | hr_manager |
| carol@apexcorp.com | Emp@123456 | employee |
| david@apexcorp.com | Emp@123456 | employee |
| eva@apexcorp.com | Read@12345 | readonly |
