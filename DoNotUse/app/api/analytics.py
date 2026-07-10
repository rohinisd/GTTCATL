from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.reports import MonthlyReport, ReportStatusEnum
from app.models.hierarchy import School
from app.core.security import require_any
from app.core.settings_store import get_current_academic_year
from app.services.aggregator import get_aggregated_kpis, get_monthly_trend, get_scoped_reports

router = APIRouter()


def _resolve_year(db, academic_year):
    # Explicit query param wins; otherwise use the admin-set global academic year.
    return academic_year or get_current_academic_year(db)


@router.get("/kpis")
def kpis(
    academic_year: str = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    academic_year = _resolve_year(db, academic_year)
    stats = get_aggregated_kpis(db, current_user, academic_year=academic_year, month=month)
    from app.services.aggregator import get_scoped_schools
    # Role-scoped school count (admin/division=all, master=their districts, trainer/principal=their school)
    total_schools = get_scoped_schools(db, current_user).filter(School.is_active == True).count()

    submitted_q = get_scoped_reports(db, current_user).filter(
        MonthlyReport.academic_year == academic_year,
        MonthlyReport.status == ReportStatusEnum.submitted,
    )
    if month:
        submitted_q = submitted_q.filter(MonthlyReport.report_month == month)
    submitted_schools = submitted_q.with_entities(
        func.count(func.distinct(MonthlyReport.school_id))
    ).scalar() or 0

    return {
        **stats,
        "academic_year": academic_year,
        "total_schools": total_schools,
        "submitted_schools": submitted_schools,
        "pending_schools": max(0, total_schools - submitted_schools),
        "submission_rate": round(submitted_schools / total_schools * 100, 1) if total_schools else 0,
    }


@router.get("/trend")
def monthly_trend(
    academic_year: str = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    academic_year = _resolve_year(db, academic_year)
    return get_monthly_trend(db, current_user, academic_year, month=month)


@router.get("/top-schools")
def top_schools(
    academic_year: str = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    metric: str = Query("students_school"),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    academic_year = _resolve_year(db, academic_year)

    q = get_scoped_reports(db, current_user).filter(
        MonthlyReport.academic_year == academic_year,
        MonthlyReport.status == ReportStatusEnum.submitted,
    )
    if month:
        q = q.filter(MonthlyReport.report_month == month)
    reports = q.all()

    # Reports are running YTD totals — use the latest report per school (no month summing)
    latest = {}
    for r in reports:
        ym = r.report_year * 100 + r.report_month
        if r.school_id not in latest or ym > latest[r.school_id][0]:
            latest[r.school_id] = (ym, r)

    def metric_val(r):
        return {
            "students_school":       r.total_students,
            "students":              r.total_students,
            "workshops_count":       r.workshops_count,
            "innovation_projects":   r.innovation_projects,
            "atl_competitions_won":  r.atl_competitions_won or 0,
            "other_competitions_won":r.other_competitions_won or 0,
        }.get(metric, r.total_students)

    rows = [
        {"school_id": r.school_id,
         "school_name": r.school.name if r.school else "",
         "district": r.school.district if r.school else "",
         "total": int(metric_val(r) or 0)}
        for _, r in latest.values()
    ]
    rows.sort(key=lambda x: x["total"], reverse=True)
    return rows[:limit]


@router.get("/leaderboard")
def leaderboard(
    academic_year: str = Query(None),
    metric: str = Query("students", pattern="^(students|workshops|projects|wins|industrial_visits)$"),
    division_id: Optional[int] = Query(None),
    district: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    from app.models.hierarchy import Division
    academic_year = _resolve_year(db, academic_year)

    def metric_val(r):
        return {
            "students":          r.total_students,
            "workshops":         r.workshops_count,
            "projects":          r.innovation_projects,
            "wins":              r.total_won,
            "industrial_visits": (r.industrial_visits or 0),
        }.get(metric, r.total_students)

    def rank_for_year(year):
        if not year:
            return {}
        q = get_scoped_reports(db, current_user).filter(
            MonthlyReport.academic_year == year,
            MonthlyReport.status == ReportStatusEnum.submitted,
        )
        if division_id: q = q.filter(School.division_id == division_id)
        if district:    q = q.filter(School.district == district)
        reports = q.all()
        # Latest report per school (running YTD totals — don't sum months)
        latest = {}
        for r in reports:
            ym = r.report_year * 100 + r.report_month
            if r.school_id not in latest or ym > latest[r.school_id][0]:
                latest[r.school_id] = (ym, r)
        ranked = sorted(
            ([r for _, r in latest.values()]),
            key=lambda r: metric_val(r), reverse=True,
        )[:limit]
        return {r.school_id: {"rank": i+1, "total": int(metric_val(r) or 0),
                              "school_name": r.school.name if r.school else "",
                              "district": r.school.district if r.school else "",
                              "division_id": r.school.division_id if r.school else None}
                for i, r in enumerate(ranked)}

    # Previous academic year (e.g. "2025-26" → "2024-25")
    try:
        start = int(academic_year.split("-")[0])
        prev_year = f"{start-1}-{str(start).zfill(2)[-2:]}"
    except Exception:
        prev_year = None

    current_ranks = rank_for_year(academic_year)
    prev_ranks    = rank_for_year(prev_year) if prev_year else {}

    result = []
    for sid, info in current_ranks.items():
        prev = prev_ranks.get(sid)
        rank_change = (prev["rank"] - info["rank"]) if prev else None  # positive = moved up
        result.append({
            "rank":         info["rank"],
            "school_id":    sid,
            "school_name":  info["school_name"],
            "district":     info["district"],
            "division_id":  info["division_id"],
            "total":        info["total"],
            "rank_change":  rank_change,
            "is_new":       prev is None,
        })

    return {"academic_year": academic_year, "metric": metric, "schools": result}


@router.get("/yoy")
def year_over_year(
    academic_year: str = Query(None),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    academic_year = _resolve_year(db, academic_year)
    try:
        start = int(academic_year.split("-")[0])
        prev_year = f"{start-1}-{str(start).zfill(2)[-2:]}"
    except Exception:
        prev_year = None

    def get_trend(year):
        rows = get_scoped_reports(db, current_user).filter(
            MonthlyReport.academic_year == year,
            MonthlyReport.status == ReportStatusEnum.submitted,
        ).with_entities(
            MonthlyReport.report_month,
            func.coalesce(func.sum(MonthlyReport.students_school + MonthlyReport.students_community), 0).label("students"),
            func.coalesce(func.sum(MonthlyReport.workshops_school + MonthlyReport.workshops_community), 0).label("workshops"),
            func.coalesce(func.sum(MonthlyReport.innovation_school + MonthlyReport.innovation_community), 0).label("projects"),
            func.count(func.distinct(MonthlyReport.school_id)).label("schools"),
        ).group_by(MonthlyReport.report_month).order_by(MonthlyReport.report_month).all()
        return {r.report_month: {"students": int(r.students), "workshops": int(r.workshops),
                                  "projects": int(r.projects), "schools": int(r.schools)}
                for r in rows}

    curr = get_trend(academic_year)
    prev = get_trend(prev_year) if prev_year else {}

    def totals(data):
        return {k: sum(v[k] for v in data.values()) for k in ("students","workshops","projects","schools")}

    curr_totals = totals(curr)
    prev_totals = totals(prev)

    def pct_change(a, b):
        if not b: return None
        return round((a - b) / b * 100, 1)

    return {
        "current_year": academic_year,
        "prev_year":    prev_year,
        "current":      curr,
        "prev":         prev,
        "current_totals": curr_totals,
        "prev_totals":    prev_totals,
        "growth": {
            "students":  pct_change(curr_totals["students"],  prev_totals["students"]),
            "workshops": pct_change(curr_totals["workshops"], prev_totals["workshops"]),
            "projects":  pct_change(curr_totals["projects"],  prev_totals["projects"]),
        },
    }
