from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import require_any
from app.core.settings_store import get_current_academic_year
from app.services.aggregator import get_aggregated_kpis, get_monthly_trend

router = APIRouter()


@router.get("/current-year")
def current_year(
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """The global academic year — used by every dashboard to scope its data."""
    return {"academic_year": get_current_academic_year(db)}


@router.get("/summary")
def dashboard_summary(
    academic_year: str = Query(None),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    # Default to the admin-set global academic year (falls back to latest data).
    if not academic_year:
        academic_year = get_current_academic_year(db)

    kpis = get_aggregated_kpis(db, current_user, academic_year=academic_year)
    trend = get_monthly_trend(db, current_user, academic_year)
    return {"kpis": kpis, "trend": trend, "academic_year": academic_year}
