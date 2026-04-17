"""
Main FastAPI application — Personal Finance Intelligence Platform.
"""
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings
from app.database import init_db, get_db
from app.routers import upload, statements, ml, auth
from app.routers import accounts, categories, advisor, budgets, reports
from app.routers import daily_expenses, daily_income, liabilities
from app.utils.page_auth import require_login
from sqlalchemy.ext.asyncio import AsyncSession


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # 1. Initialize database (Alembic migrations + create_all fallback)
    await init_db()
    print(f"✓ Database initialized: {settings.database_url}")

    # 2. Seed financial institutions (idempotent)
    try:
        from app.database import AsyncSessionLocal
        from app.services.seed_data import seed_institutions
        async with AsyncSessionLocal() as db:
            await seed_institutions(db)
        print("✓ Financial institutions seeded")
    except Exception as e:
        print(f"⚠ Institution seeding failed: {e}")

    # 3. Seed category rules (idempotent)
    try:
        from app.database import AsyncSessionLocal
        from app.services.category_engine import seed_category_rules
        async with AsyncSessionLocal() as db:
            await seed_category_rules(db)
        print("✓ Category rules seeded")
    except Exception as e:
        print(f"⚠ Category rule seeding failed: {e}")

    # 4. Start background scheduler
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
        print("✓ Background scheduler started")
    except Exception as e:
        print(f"⚠ Scheduler failed to start: {e}")

    print(f"✓ Upload directory: {settings.upload_dir}")
    print(f"✓ Claude Vision: {'enabled' if settings.anthropic_api_key else 'disabled (set ANTHROPIC_API_KEY)'}")
    print(f"✓ Server starting on {settings.host}:{settings.port}")

    yield

    # Shutdown
    try:
        from app.services.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass
    print("✓ Server shutting down")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered personal finance platform: "
        "parse multi-bank statements, track spending across cards, "
        "and get personalized financial insights."
    ),
    version=settings.app_version,
    lifespan=lifespan
)

# Add session middleware for web authentication
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie="pfi_session",
    max_age=86400 * 7,  # 7 days
    same_site="lax",
    https_only=settings.is_production,
)

# Add security headers to all responses
app.add_middleware(SecurityHeadersMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates (globals available on every page)
templates = Jinja2Templates(directory="templates")
templates.env.globals["app_name"] = settings.app_name
templates.env.globals["app_version"] = settings.app_version
templates.env.globals["google_oauth_client_id"] = settings.google_oauth_client_id or ""

# ---------------------------------------------------------------------------
# API routers
# ---------------------------------------------------------------------------
app.include_router(auth.router)        # Authentication (login/logout)
app.include_router(upload.router)
app.include_router(statements.router)
app.include_router(ml.router)          # Legacy ML router (kept for backward compat)
app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(advisor.router)
app.include_router(budgets.router)
app.include_router(reports.router)
app.include_router(daily_expenses.router)
app.include_router(daily_income.router)
app.include_router(liabilities.router)


# ---------------------------------------------------------------------------
# HTML page routes
# ---------------------------------------------------------------------------

# Public auth pages (no login required)
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page - redirects to dashboard if already logged in"""
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Signup page - redirects to dashboard if already logged in"""
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "signup.html", {"title": "Sign Up"})


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Forgot password page"""
    return templates.TemplateResponse(request, "forgot_password.html", {"title": "Forgot Password"})


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    """Reset password page (with token in query params)"""
    return templates.TemplateResponse(request, "reset_password.html", {"title": "Reset Password"})


# Protected pages (require login)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    """Home page - upload statement (requires login)"""
    user = await require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "index.html", {"title": "Upload Statement", "user": user})


@app.get("/statements", response_class=HTMLResponse)
async def statements_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Statements list page (requires login)"""
    user = await require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "statement_list.html", {"title": "Statements", "user": user})


@app.get("/statements/{statement_id}", response_class=HTMLResponse)
async def statement_detail_page(request: Request, statement_id: int, db: AsyncSession = Depends(get_db)):
    """Statement detail page (requires login)"""
    user = await require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request, "statement_detail.html",
        {"title": "Statement Detail", "statement_id": statement_id, "user": user}
    )


@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Reports page (requires login)"""
    user = await require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "reports.html", {"title": "Reports", "user": user})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Dashboard page (requires login)"""
    user = await require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "dashboard.html", {"title": "Dashboard", "user": user})


@app.get("/preview", response_class=HTMLResponse)
async def preview_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Preview statement page (requires login)"""
    user = await require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "preview.html", {"title": "Preview Statement", "user": user})


@app.get("/transactions", response_class=HTMLResponse)
async def all_transactions_page(request: Request, db: AsyncSession = Depends(get_db)):
    """All transactions page (requires login)"""
    user = await require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "all_transactions.html", {"title": "All Transactions", "user": user})


@app.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Accounts page (requires login)"""
    user = await require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "accounts.html", {"title": "My Cards & Accounts", "user": user})


@app.get("/advisor", response_class=HTMLResponse)
async def advisor_page(request: Request, db: AsyncSession = Depends(get_db)):
    """AI Advisor page (requires login)"""
    user = await require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "advisor.html", {"title": "AI Advisor", "user": user})


@app.get("/daily-expenses", response_class=HTMLResponse)
async def daily_expenses_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Daily expenses page (requires login)"""
    user = await require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "daily_expenses.html", {"title": "Daily Expenses", "user": user})


@app.get("/daily-income", response_class=HTMLResponse)
async def daily_income_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Income tracker page (requires login)"""
    user = await require_login(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "daily_income.html", {"title": "Income Tracker", "user": user})


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "claude_vision": bool(settings.anthropic_api_key),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
