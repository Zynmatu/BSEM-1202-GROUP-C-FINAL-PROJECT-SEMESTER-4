"""
main.py — FastAPI application factory for the HR Management System.

Wires together:
  • Database initialisation on startup
  • All API routers
  • Custom Swagger UI (/docs) and branded ReDoc (/redoc + /docs/hr)
  • CORS, GZip, static files
  • Global exception handlers
"""
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import auth, users, employees, departments, roles, payroll, leave, pages

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀  Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    await init_db()
    logger.info("✅  Database tables verified / created")
    yield
    logger.info("🛑  Shutting down %s", settings.APP_NAME)


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Human Resource Management API

A production-ready REST API for managing the complete HR lifecycle:

| Module | Endpoints |
|---|---|
| 🔐 **Auth** | Register, Login (OAuth2 + JWT), Refresh, Me |
| 👤 **Users** | CRUD + role management |
| 👥 **Employees** | CRUD + async external enrichment |
| 🏢 **Departments** | CRUD |
| 💼 **Roles** | CRUD |
| 💰 **Payroll** | CRUD + auto net-pay calculation |
| 🏖️ **Leave** | Submit, review (approve/reject), CRUD |

### Authentication
All protected endpoints require a **Bearer JWT** token obtained from `/auth/token` (OAuth2 Password flow) or `/auth/login` (JSON body).

### Roles
| Role | Access |
|---|---|
| `admin` | Full access |
| `hr_manager` | Read + write employees, payroll, leave |
| `employee` | Read own profile, submit leave |
| `readonly` | Read-only |
""",
    openapi_url="/openapi.json",
    docs_url=None,     # We serve custom Swagger UI
    redoc_url=None,    # We serve custom ReDoc
    lifespan=lifespan,
    contact={
        "name": settings.COMPANY_NAME,
        "email": settings.SUPPORT_EMAIL,
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)


# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{(time.perf_counter() - start) * 1000:.2f}ms"
    return response


# ── Static files ──────────────────────────────────────────────────────────────
static_dir = Path(__file__).parent.parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ── License endpoint ──────────────────────────────────────────────────────────
license_path = Path(__file__).parent.parent / "LICENSE.txt"

@app.get("/LICENSE.txt", include_in_schema=False)
async def license_file():
    return FileResponse(license_path, media_type="text/plain")


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(employees.router)
app.include_router(departments.router)
app.include_router(roles.router)
app.include_router(payroll.router)
app.include_router(leave.router)
app.include_router(pages.router)


# ── Custom Swagger UI (/docs) ─────────────────────────────────────────────────
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui() -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.APP_NAME} — Swagger UI",
        swagger_favicon_url="/static/favicon.svg",
        swagger_ui_parameters={
            "deepLinking": True,
            "displayRequestDuration": True,
            "defaultModelsExpandDepth": 2,
            "defaultModelExpandDepth": 3,
            "filter": True,
            "syntaxHighlight.theme": "monokai",
            "tryItOutEnabled": True,
            "persistAuthorization": True,
        },
    )


# ── Custom branded ReDoc (/redoc) — High-contrast theme ──────────────────────
REDOC_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title} — API Reference</title>
  <link rel="icon" href="/static/favicon.svg" type="image/svg+xml" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    /* ── Reset ───────────────────────────────────────────────── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --header-h: 62px;
      /* Palette */
      --navy:      #07112b;
      --navy-mid:  #0d1f45;
      --blue:      #1d4ed8;
      --blue-lt:   #3b82f6;
      --blue-pale: #eff6ff;
      --amber:     #d97706;
      --amber-lt:  #fef3c7;
      --white:     #ffffff;
      --off-white: #f8fafc;
      --slate-100: #f1f5f9;
      --slate-200: #e2e8f0;
      --slate-300: #cbd5e1;
      --slate-700: #334155;
      --slate-800: #1e293b;
      --slate-900: #0f172a;
    }}

    html, body {{ height: 100%; font-family: 'Inter', -apple-system, sans-serif; }}
    body {{ background: var(--off-white); }}

    /* ═══════════════════════════════════════════════════════════
       TOP HEADER
    ═══════════════════════════════════════════════════════════ */
    .hr-header {{
      position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
      height: var(--header-h);
      background: linear-gradient(100deg, var(--navy) 0%, var(--navy-mid) 55%, #112266 100%);
      display: flex; align-items: center; justify-content: space-between;
      padding: 0 1.75rem;
      box-shadow: 0 1px 0 rgba(255,255,255,0.06), 0 4px 24px rgba(0,0,0,0.5);
    }}

    /* Brand */
    .hdr-brand {{ display: flex; align-items: center; gap: 12px; }}
    .hdr-logo {{
      width: 36px; height: 36px; border-radius: 9px; flex-shrink: 0;
      background: linear-gradient(135deg, var(--blue) 0%, var(--blue-lt) 100%);
      display: flex; align-items: center; justify-content: center;
      font-size: 18px;
      box-shadow: 0 2px 8px rgba(29,78,216,0.5);
    }}
    .hdr-title  {{ font-size: 15px; font-weight: 800; color: #fff; letter-spacing: -0.3px; line-height: 1.1; }}
    .hdr-sub    {{ font-size: 10px; color: rgba(255,255,255,0.45); letter-spacing: 1.2px; text-transform: uppercase; margin-top: 1px; }}

    /* Nav links */
    .hdr-nav {{ display: flex; align-items: center; gap: 2px; }}
    .hdr-nav a {{
      color: rgba(255,255,255,0.65); text-decoration: none;
      font-size: 12.5px; font-weight: 500;
      padding: 6px 13px; border-radius: 7px;
      transition: background 0.15s, color 0.15s;
      white-space: nowrap;
    }}
    .hdr-nav a:hover {{ background: rgba(255,255,255,0.1); color: #fff; }}
    .hdr-nav a.active {{
      background: rgba(255,255,255,0.14);
      color: #fff; font-weight: 600;
    }}

    /* Right cluster */
    .hdr-right {{ display: flex; align-items: center; gap: 10px; }}
    .hdr-badge {{
      background: var(--amber); color: #0f172a;
      font-size: 11px; font-weight: 800;
      padding: 3px 11px; border-radius: 20px; letter-spacing: 0.4px;
    }}
    .hdr-pill {{
      display: flex; align-items: center; gap: 5px;
      background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12);
      border-radius: 20px; padding: 4px 12px;
      font-size: 11.5px; color: rgba(255,255,255,0.6);
    }}
    .hdr-dot {{
      width: 7px; height: 7px; border-radius: 50%; background: #22c55e;
      box-shadow: 0 0 0 2px rgba(34,197,94,0.3);
      animation: glow 2s ease-in-out infinite;
    }}
    @keyframes glow {{
      0%,100% {{ box-shadow: 0 0 0 2px rgba(34,197,94,0.25); }}
      50%      {{ box-shadow: 0 0 0 5px rgba(34,197,94,0.1); }}
    }}

    /* ═══════════════════════════════════════════════════════════
       REDOC MOUNT POINT
    ═══════════════════════════════════════════════════════════ */
    #redoc-mount {{
      margin-top: var(--header-h);
      min-height: calc(100vh - var(--header-h));
    }}

    /* ═══════════════════════════════════════════════════════════
       REDOC DOM OVERRIDES
       (injected after render via <style> so they win specificity)
    ═══════════════════════════════════════════════════════════ */
    /* Sidebar — keep dark navy for strong contrast with white content */
    [data-role="search-input"] {{
      background: rgba(255,255,255,0.08) !important;
      color: #fff !important;
      border: 1px solid rgba(255,255,255,0.15) !important;
    }}

    /* Make the main content panel true white */
    .api-content {{ background: #ffffff !important; }}

    /* Sharper heading colour */
    h1, h2, h3 {{ color: var(--slate-900) !important; }}

    /* Responsive: hide nav links on small screens */
    @media (max-width: 860px) {{
      .hdr-nav {{ display: none; }}
      .hdr-right .hdr-pill {{ display: none; }}
    }}
  </style>
</head>
<body>

<!-- ══ Header ═══════════════════════════════════════════════════════ -->
<header class="hr-header">
  <div class="hdr-brand">
    <div class="hdr-logo">🏢</div>
    <div>
      <div class="hdr-title">{company}</div>
      <div class="hdr-sub">Human Resources API</div>
    </div>
  </div>

  <nav class="hdr-nav">
    <a href="/dashboard">Dashboard</a>
    <a href="/docs">Swagger UI</a>
    <a href="/redoc" class="active">API Reference</a>
    <a href="/database-viewer">Database</a>
    <a href="/support">Support</a>
  </nav>

  <div class="hdr-right">
    <div class="hdr-pill"><span class="hdr-dot"></span> Live</div>
    <div class="hdr-badge">v{version}</div>
  </div>
</header>

<!-- ══ ReDoc ═════════════════════════════════════════════════════════ -->
<div id="redoc-mount"></div>

<script src="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"></script>
<script>
  Redoc.init(
    "/openapi.json",
    {{
      /* ── Behaviour ─────────────────────────────────────────── */
      hideDownloadButton:       false,
      expandResponses:          "200,201",
      requiredPropsFirst:       true,
      sortPropsAlphabetically:  false,
      noAutoAuth:               false,
      pathInMiddlePanel:        false,
      lazyRendering:            true,
      hideHostname:             false,
      expandSingleSchemaField:  true,
      showExtensions:           false,
      jsonSampleExpandLevel:    2,
      hideSchemaTitles:         false,
      simpleOneOfTypeLabel:     true,

      /* ── Theme ─────────────────────────────────────────────── */
      theme: {{

        /* Main colours */
        colors: {{
          primary:  {{ main: "#1d4ed8" }},
          success:  {{ main: "#16a34a" }},
          warning:  {{ main: "#d97706" }},
          error:    {{ main: "#dc2626" }},
          /* High-contrast body text on white */
          text: {{
            primary:   "#0f172a",   /* near-black — WCAG AAA on white */
            secondary: "#334155"    /* dark slate — WCAG AA on white */
          }},
          border: {{
            dark:  "#94a3b8",
            light: "#e2e8f0"
          }},
          /* Response-panel tints — vivid but readable */
          responses: {{
            success:  {{ color: "#15803d", backgroundColor: "#f0fdf4", tabTextColor: "#14532d" }},
            error:    {{ color: "#b91c1c", backgroundColor: "#fff1f2", tabTextColor: "#7f1d1d" }},
            redirect: {{ color: "#b45309", backgroundColor: "#fffbeb", tabTextColor: "#78350f" }},
            info:     {{ color: "#1d4ed8", backgroundColor: "#eff6ff", tabTextColor: "#1e3a8a" }}
          }},
          /* HTTP verb badges — high-saturation, dark text on light bg */
          http: {{
            get:     "#16a34a",   /* green  */
            post:    "#1d4ed8",   /* blue   */
            put:     "#d97706",   /* amber  */
            patch:   "#7c3aed",   /* violet */
            delete:  "#dc2626",   /* red    */
            head:    "#475569",
            options: "#475569"
          }}
        }},

        /* Typography — Inter for prose, JetBrains Mono for code */
        typography: {{
          fontSize:       "15px",
          lineHeight:     "1.7",
          fontWeightBold: "700",
          fontFamily:     "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
          smoothing:      "antialiased",
          headings: {{
            fontFamily: "Inter, sans-serif",
            fontWeight: "800",
            lineHeight: "1.3"
          }},
          code: {{
            fontSize:        "13px",
            fontFamily:      "JetBrains Mono, Menlo, monospace",
            lineHeight:      "1.6",
            fontWeight:      "400",
            /* High-contrast inline code: dark text on very-light blue */
            color:           "#0f172a",
            backgroundColor: "#e8f0fe",
            wrap:            true
          }}
        }},

        /* Sidebar — deep navy for max contrast against white content */
        sidebar: {{
          width:           "290px",
          backgroundColor: "#07112b",
          textColor:       "#cbd5e1"   /* light slate — WCAG AA on #07112b */
        }},

        /* Right panel (code samples) — dark navy complements white middle */
        rightPanel: {{
          backgroundColor: "#0d1f45",
          width:           "38%",
          textColor:       "#e2e8f0"
        }},

        /* Code blocks inside right panel */
        codeBlock: {{
          backgroundColor: "#07112b"
        }},

        logo: {{ maxHeight: "40px", maxWidth: "200px", gutter: "16px" }}
      }}
    }},
    document.getElementById("redoc-mount")
  );
</script>
</body>
</html>"""


@app.get("/redoc", include_in_schema=False)
async def custom_redoc() -> HTMLResponse:
    return HTMLResponse(
        REDOC_HTML.format(
            title=settings.APP_NAME,
            company=settings.COMPANY_NAME,
            version=settings.APP_VERSION,
        )
    )


# Alias: /docs/hr points to the same branded ReDoc
@app.get("/docs/hr", include_in_schema=False)
async def hr_docs() -> HTMLResponse:
    return await custom_redoc()


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], summary="Health check")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# ── Root redirect ─────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


# ── Global exception handlers ─────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found_handler(request: Request, exc) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found", "path": str(request.url.path)},
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
