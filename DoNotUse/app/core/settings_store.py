"""Global portal settings — single source of truth for the current academic year.

The admin sets the academic year in Settings; it is persisted in the
``system_settings`` table and every dashboard's data (cards, charts, tables)
is filtered by it. If unset, we fall back to the latest year that has report
data, then to the computed current academic year (Indian school year: Jun→May).
"""
from datetime import date
from sqlalchemy.orm import Session

ACADEMIC_YEAR_KEY = "academic_year"
REPORT_DEADLINE_KEY = "report_deadline_day"


def computed_current_year() -> str:
    """Indian academic year for today — runs June → May."""
    today = date.today()
    y = today.year
    return f"{y}-{str(y + 1)[2:]}" if today.month >= 6 else f"{y - 1}-{str(y)[2:]}"


def get_setting(db: Session, key: str, default=None):
    from app.models.reports import SystemSetting
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return row.value if row and row.value is not None else default


def set_setting(db: Session, key: str, value: str) -> None:
    from app.models.reports import SystemSetting
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=str(value)))
    db.commit()


def get_current_academic_year(db: Session) -> str:
    """The global academic year: admin-set value → latest year with data → computed."""
    val = get_setting(db, ACADEMIC_YEAR_KEY)
    if val:
        return val
    from app.models.reports import MonthlyReport
    latest = (
        db.query(MonthlyReport.academic_year)
        .order_by(MonthlyReport.report_year.desc(), MonthlyReport.report_month.desc())
        .first()
    )
    return latest[0] if latest else computed_current_year()
