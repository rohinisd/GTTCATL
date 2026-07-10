from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

from app.database import engine, Base
from app.api import auth, dashboard, admin, reports, users, schools, analytics, export, upload, gallery, inventory, attendance, leave
from app.models import attendance as _attendance_models  # ensure table is registered
from app.models import leave as _leave_models            # ensure tables are registered (incl. PayrollAdjustment)
from app.core.seed import seed_initial_data

logger = logging.getLogger(__name__)

# ── Create all tables ──────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── Lightweight migration: add columns missing from existing SQLite DB ──
def _ensure_columns():
    from sqlalchemy import inspect, text
    insp = inspect(engine)

    def add_missing(table, cols):
        try:
            existing = {c["name"] for c in insp.get_columns(table)}
        except Exception:
            return
        with engine.begin() as conn:
            for col, decl in cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {decl}"))
                    logger.info("Migration: added %s.%s", table, col)

    add_missing("monthly_reports", {"ip_granted": "INTEGER DEFAULT 0", "ip_filed": "INTEGER DEFAULT 0"})
    add_missing("report_used_items", {"usage_count": "INTEGER NOT NULL DEFAULT 1"})
    add_missing("division_targets", {
        "target_atl_comp":    "INTEGER DEFAULT 0",
        "target_other_comp":  "INTEGER DEFAULT 0",
        "target_mentoring":   "INTEGER DEFAULT 0",
        "target_exhibitions": "INTEGER DEFAULT 0",
    })
    add_missing("equipment_inventory", {
        "issued_by":           "INTEGER",
        "issued_at":           "DATETIME",
        "working_qty":         "INTEGER",
        "not_working_qty":     "INTEGER",
        "additional_required": "INTEGER",
        "review_notes":        "TEXT",
        "reviewed_by":         "INTEGER",
        "reviewed_at":         "DATETIME",
    })
    add_missing("schools", {
        "geo_latitude":       "REAL",
        "geo_longitude":      "REAL",
        "geo_radius":         "INTEGER DEFAULT 200",
        "school_start_time":  "TEXT",
        "school_end_time":    "TEXT",
    })
    add_missing("users", {
        "salary": "REAL DEFAULT 0",
    })

_ensure_columns()

app = FastAPI(
    title="GTTC Robotics Training Dashboard",
    description="5-Level Hierarchical Robotics Training Management System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files & templates ───────────────────────────────────
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ── Routers ────────────────────────────────────────────────────
app.include_router(auth.router,      prefix="/api/auth",      tags=["Auth"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(admin.router,     prefix="/api/admin",     tags=["Admin"])
app.include_router(reports.router,   prefix="/api/reports",   tags=["Reports"])
app.include_router(users.router,     prefix="/api/users",     tags=["Users"])
app.include_router(schools.router,   prefix="/api/schools",   tags=["Schools"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(export.router,    prefix="/api/export",    tags=["Export"])
app.include_router(upload.router,    prefix="/api/upload",    tags=["Upload"])
app.include_router(gallery.router,   prefix="/api/gallery",   tags=["Gallery"])
app.include_router(inventory.router,   prefix="/api/inventory",   tags=["Inventory"])
app.include_router(attendance.router,  prefix="/api/attendance",  tags=["Attendance"])
app.include_router(leave.router,       prefix="/api/leave",       tags=["Leave & Holidays"])

# ── Page routes (serve SPA shell) ─────────────────────────────
@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(request, "landing.html")

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.get("/{full_path:path}")
async def spa_shell(request: Request, full_path: str):
    role_templates = {
        "admin":    "admin_dash.html",
        "division": "division_dash.html",
        "master":   "master_dash.html",
        "trainer":  "trainer_dash.html",
        "principal":"principal_dash.html",
    }
    template = role_templates.get(full_path.split("/")[0], "admin_dash.html")
    return templates.TemplateResponse(request, template)

# ── Automated reminder job ─────────────────────────────────────
def send_pending_report_reminders():
    from datetime import date
    from app.database import SessionLocal
    from app.models.reports import MonthlyReport, ReportStatusEnum, Notification
    from app.models.hierarchy import School, SchoolTrainer
    from app.models.users import User, RoleEnum

    db = SessionLocal()
    try:
        today = date.today()
        year, month = today.year, today.month
        # Academic year: April=start of new year
        if month >= 4:
            academic_year = f"{year}-{str(year + 1)[2:]}"
        else:
            academic_year = f"{year - 1}-{str(year)[2:]}"

        # Schools that have NOT submitted for this month
        submitted_ids = {
            r.school_id for r in db.query(MonthlyReport.school_id).filter(
                MonthlyReport.report_year == year,
                MonthlyReport.report_month == month,
                MonthlyReport.status == ReportStatusEnum.submitted,
            ).all()
        }
        all_school_ids = {s.id for s in db.query(School.id).filter(School.is_active == True).all()}
        pending_ids = all_school_ids - submitted_ids

        created = 0
        for school_id in pending_ids:
            # Notify all trainers linked to this school
            trainer_links = db.query(SchoolTrainer).filter(SchoolTrainer.school_id == school_id).all()
            school = db.query(School).filter(School.id == school_id).first()
            for link in trainer_links:
                notif = Notification(
                    user_id=link.trainer_id,
                    title="Monthly Report Reminder",
                    body=f"Report for {school.name} ({month}/{year}) is still pending. Please submit before the deadline.",
                    notif_type="pending_report",
                    link_page="reports",
                )
                db.add(notif)
                created += 1

        db.commit()
        logger.info("Auto-reminder: created %d notifications for %d pending schools (%d/%d)",
                    created, len(pending_ids), month, year)
    except Exception:
        logger.exception("Auto-reminder job failed")
        db.rollback()
    finally:
        db.close()


_scheduler = BackgroundScheduler(daemon=True)
# 8th and 10th of every month at 08:00
_scheduler.add_job(send_pending_report_reminders, CronTrigger(day="8,10", hour=8, minute=0),
                   id="pending_reminders", replace_existing=True)


# ── Startup: seed default state admin ─────────────────────────
@app.on_event("startup")
async def startup_event():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        seed_initial_data(db)
        from app.core.seed_projects import seed_projects
        seed_projects(db)
    finally:
        db.close()
    _scheduler.start()
    logger.info("APScheduler started — reminder jobs: %s", [str(j) for j in _scheduler.get_jobs()])


@app.on_event("shutdown")
async def shutdown_event():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
