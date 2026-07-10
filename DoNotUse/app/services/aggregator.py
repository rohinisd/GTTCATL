from sqlalchemy import func
from sqlalchemy.orm import Session, Query
from app.models.reports import MonthlyReport
from app.models.hierarchy import School, SchoolTrainer, SchoolPrincipal
from app.models.users import RoleEnum


def get_scoped_schools(db: Session, current_user) -> Query:
    q = db.query(School)
    if current_user.role == RoleEnum.master_trainer:
        districts = current_user.districts or []
        q = q.filter(School.district.in_(districts)) if districts else q.filter(False)
    elif current_user.role == RoleEnum.atl_trainer:
        ids = [st.school_id for st in db.query(SchoolTrainer).filter(
            SchoolTrainer.user_id == current_user.id,
            SchoolTrainer.is_current == True,
        ).all()]
        q = q.filter(School.id.in_(ids))
    elif current_user.role == RoleEnum.principal:
        ids = [sp.school_id for sp in db.query(SchoolPrincipal).filter(
            SchoolPrincipal.user_id == current_user.id,
            SchoolPrincipal.is_current == True,
        ).all()]
        q = q.filter(School.id.in_(ids))
    return q


def _assignment_filter(links):
    """Build an OR of (school_id == X AND report-month >= assigned_from-month) for
    each of the user's current school assignments.

    A trainer/principal only sees reports for their school(s) FROM THE MONTH THEY
    WERE ASSIGNED onward — so a freshly-created user starts with a clean slate and
    accumulates data only as they submit it, instead of inheriting the school's
    pre-existing history.
    """
    from sqlalchemy import or_, and_, false
    conds = []
    for link in links:
        cond = MonthlyReport.school_id == link.school_id
        af = link.assigned_from
        if af:
            key = af.year * 12 + (af.month - 1)
            cond = and_(cond, (MonthlyReport.report_year * 12 + (MonthlyReport.report_month - 1)) >= key)
        conds.append(cond)
    return or_(*conds) if conds else false()


def get_scoped_reports(db: Session, current_user) -> Query:
    q = db.query(MonthlyReport).join(School, MonthlyReport.school_id == School.id)
    if current_user.role == RoleEnum.master_trainer:
        districts = current_user.districts or []
        if districts:
            q = q.filter(School.district.in_(districts))
        else:
            q = q.filter(False)
    elif current_user.role == RoleEnum.atl_trainer:
        links = db.query(SchoolTrainer).filter(
            SchoolTrainer.user_id == current_user.id,
            SchoolTrainer.is_current == True,
        ).all()
        q = q.filter(_assignment_filter(links))
    elif current_user.role == RoleEnum.principal:
        links = db.query(SchoolPrincipal).filter(
            SchoolPrincipal.user_id == current_user.id,
            SchoolPrincipal.is_current == True,
        ).all()
        q = q.filter(_assignment_filter(links))
    return q


def get_aggregated_kpis(db: Session, current_user, academic_year: str = None, month: int = None):
    from app.models.reports import ReportStatusEnum
    q = get_scoped_reports(db, current_user).filter(
        MonthlyReport.status == ReportStatusEnum.submitted
    )
    if academic_year:
        q = q.filter(MonthlyReport.academic_year == academic_year)
    if month:
        q = q.filter(MonthlyReport.report_month == month)

    all_reports = q.all()

    # Each report is a running YTD total — use only the latest report per school
    latest_by_school = {}
    for r in all_reports:
        ym = r.report_year * 100 + r.report_month
        prev = latest_by_school.get(r.school_id)
        if prev is None or ym > prev[0]:
            latest_by_school[r.school_id] = (ym, r)

    latest = [v[1] for v in latest_by_school.values()]

    total_students       = sum((r.students_school or 0) + (r.students_community or 0) for r in latest)
    total_girls          = sum(r.students_girls or 0 for r in latest)
    total_boys           = max(0, total_students - total_girls)
    total_workshops      = sum((r.workshops_school or 0) + (r.workshops_community or 0) for r in latest)
    total_projects       = sum((r.innovation_school or 0) + (r.innovation_community or 0) for r in latest)
    total_wins           = sum((r.atl_competitions_won or 0) + (r.other_competitions_won or 0) for r in latest)
    total_mentoring      = sum((r.mentoring_school or 0) + (r.mentoring_community or 0) for r in latest)
    atl_participants     = sum(r.atl_competitions_participated or 0 for r in latest)
    other_participants   = sum(r.other_competitions_participated or 0 for r in latest)
    total_patents        = sum((r.patents_school or 0) + (r.patents_community or 0) for r in latest)
    total_copyrights     = sum((r.copyrights_school or 0) + (r.copyrights_community or 0) for r in latest)
    total_ip_granted     = sum(getattr(r, "ip_granted", 0) or 0 for r in latest)
    total_ip_filed       = sum(getattr(r, "ip_filed", 0) or 0 for r in latest)
    industrial_visits    = sum(r.industrial_visits or 0 for r in latest)
    active_labs          = len(latest_by_school)

    # ATL competition events count
    from app.models.reports import ATLCompetition
    atl_competition_events = db.query(ATLCompetition).count()

    return {
        "total_students":        total_students,
        "total_girls":           total_girls,
        "total_boys":            total_boys,
        "total_workshops":       total_workshops,
        "total_projects":        total_projects,
        "total_wins":            total_wins,
        "total_mentoring":       total_mentoring,
        "atl_participants":      atl_participants,
        "other_participants":    other_participants,
        "total_patents":         total_patents,
        "total_copyrights":      total_copyrights,
        "total_ip_granted":      total_ip_granted,
        "total_ip_filed":        total_ip_filed,
        "industrial_visits":     industrial_visits,
        "active_labs":           active_labs,
        "atl_competition_events":atl_competition_events,
        "total_reports":         len(all_reports),
        "reporting_schools":     len(latest_by_school),
    }


def get_monthly_trend(db: Session, current_user, academic_year: str, month: int = None):
    from app.models.reports import ReportStatusEnum
    q = get_scoped_reports(db, current_user).filter(
        MonthlyReport.academic_year == academic_year,
        MonthlyReport.status == ReportStatusEnum.submitted,
    )
    if month:
        q = q.filter(MonthlyReport.report_month == month)
    rows = q.with_entities(
        MonthlyReport.report_month,
        func.coalesce(func.sum(MonthlyReport.students_school + MonthlyReport.students_community), 0).label("students"),
        func.coalesce(func.sum(MonthlyReport.workshops_school + MonthlyReport.workshops_community), 0).label("workshops"),
        func.coalesce(func.sum(MonthlyReport.innovation_school + MonthlyReport.innovation_community), 0).label("projects"),
        func.count(func.distinct(MonthlyReport.school_id)).label("schools"),
    ).group_by(MonthlyReport.report_month).all()
    data = [
        {
            "month": r.report_month,
            "students": int(r.students),
            "workshops": int(r.workshops),
            "projects": int(r.projects),
            "schools": int(r.schools),
        }
        for r in rows
    ]
    # Indian school academic year runs June → May, so order the series
    # Jun(6)…Dec(12), then Jan(1)…May(5) instead of plain calendar order.
    data.sort(key=lambda d: (d["month"] - 6) % 12)
    return data
