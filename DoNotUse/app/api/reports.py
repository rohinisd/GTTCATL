from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reports import MonthlyReport, ReportStatusEnum, Notification
from app.models.hierarchy import School, SchoolTrainer
from app.models.users import User, RoleEnum
from app.schemas.report_schema import ReportCreate, ReportUpdate
from app.core.security import get_current_user, require_any, require_sub_and_above
from app.services.aggregator import get_scoped_reports

router = APIRouter()

MONTH_NAMES = ["","January","February","March","April","May","June",
               "July","August","September","October","November","December"]


@router.get("")
def list_reports(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    school_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(100, le=500),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    q = get_scoped_reports(db, current_user)
    if year:          q = q.filter(MonthlyReport.report_year == year)
    if month:         q = q.filter(MonthlyReport.report_month == month)
    if academic_year: q = q.filter(MonthlyReport.academic_year == academic_year)
    if school_id:     q = q.filter(MonthlyReport.school_id == school_id)
    if status:        q = q.filter(MonthlyReport.status == status)
    rows = q.order_by(MonthlyReport.report_year.desc(), MonthlyReport.report_month.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": r.id, "school_id": r.school_id,
            "school_name": r.school.name if r.school else None,
            "report_year": r.report_year, "report_month": r.report_month,
            "academic_year": r.academic_year,
            "students_school": r.students_school, "students_community": r.students_community,
            "students_girls": r.students_girls,
            "workshops_school": r.workshops_school, "workshops_community": r.workshops_community,
            "workshops_count": r.workshops_count,
            "mentoring_school": r.mentoring_school, "mentoring_community": r.mentoring_community,
            "mentoring_sessions": r.mentoring_sessions,
            "innovation_school": r.innovation_school, "innovation_community": r.innovation_community,
            "innovation_projects": r.innovation_projects,
            "patents_school": r.patents_school, "patents_community": r.patents_community,
            "patents_filed": r.patents_filed,
            "copyrights_school": r.copyrights_school, "copyrights_community": r.copyrights_community,
            "copyrights_filed": r.copyrights_filed,
            "atl_competitions_participated": r.atl_competitions_participated,
            "atl_competitions_won": r.atl_competitions_won,
            "other_competitions_participated": r.other_competitions_participated,
            "other_competitions_won": r.other_competitions_won,
            "industrial_visits": r.industrial_visits,
            "ip_granted": r.ip_granted,
            "ip_filed": r.ip_filed,
            "highlight_of_month": r.highlight_of_month,
            "social_post_link_1": r.social_post_link_1,
            "social_post_link_2": r.social_post_link_2,
            "social_post_link_3": r.social_post_link_3,
            "status": r.status.value, "submitted_at": r.submitted_at,
            "total_students": r.total_students, "total_won": r.total_won,
            "reviewed_by": r.reviewed_by, "reviewed_at": r.reviewed_at,
            "review_notes": r.review_notes,
            "reviewer_name": r.reviewer.name if r.reviewer else None,
            "reviewer_role": r.reviewer.role.value if r.reviewer else None,
        }
        for r in rows
    ]


@router.post("")
def create_or_update_report(
    body: ReportCreate,
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    if current_user.role == RoleEnum.principal:
        raise HTTPException(403, "Principals cannot submit reports")
    if current_user.role == RoleEnum.atl_trainer:
        link = db.query(SchoolTrainer).filter(
            SchoolTrainer.school_id == body.school_id,
            SchoolTrainer.user_id == current_user.id,
            SchoolTrainer.is_current == True,
        ).first()
        if not link:
            raise HTTPException(403, "Not your school")

    existing = db.query(MonthlyReport).filter(
        MonthlyReport.school_id == body.school_id,
        MonthlyReport.report_year == body.report_year,
        MonthlyReport.report_month == body.report_month,
    ).first()

    if existing:
        if existing.status == ReportStatusEnum.submitted and current_user.role == RoleEnum.atl_trainer:
            raise HTTPException(400, "Already submitted. Contact Division Master (SPM GTTC) to edit.")
        for f, v in body.model_dump(exclude={"school_id"}).items():
            if v is not None:
                setattr(existing, f, v)
        report = existing
    else:
        report = MonthlyReport(**body.model_dump(), submitted_by=current_user.id)
        db.add(report)

    db.commit()
    db.refresh(report)
    return {"id": report.id, "status": report.status.value}


@router.get("/{report_id}")
def get_report(
    report_id: int, db: Session = Depends(get_db), current_user=Depends(require_any),
):
    r = db.query(MonthlyReport).filter(MonthlyReport.id == report_id).first()
    if not r: raise HTTPException(404, "Report not found")
    return {
        "id": r.id, "school_id": r.school_id,
        "school_name": r.school.name if r.school else None,
        "report_year": r.report_year, "report_month": r.report_month,
        "academic_year": r.academic_year,
        "students_school": r.students_school, "students_community": r.students_community,
        "students_girls": r.students_girls,
        "workshops_school": r.workshops_school, "workshops_community": r.workshops_community,
        "workshops_count": r.workshops_count,
        "mentoring_school": r.mentoring_school, "mentoring_community": r.mentoring_community,
        "mentoring_sessions": r.mentoring_sessions,
        "innovation_school": r.innovation_school, "innovation_community": r.innovation_community,
        "innovation_projects": r.innovation_projects,
        "patents_school": r.patents_school, "patents_community": r.patents_community,
        "patents_filed": r.patents_filed,
        "copyrights_school": r.copyrights_school, "copyrights_community": r.copyrights_community,
        "copyrights_filed": r.copyrights_filed,
        "atl_competitions_participated": r.atl_competitions_participated,
        "atl_competitions_won": r.atl_competitions_won,
        "other_competitions_participated": r.other_competitions_participated,
        "other_competitions_won": r.other_competitions_won,
        "industrial_visits": r.industrial_visits,
        "ip_granted": r.ip_granted,
        "ip_filed": r.ip_filed,
        "highlight_of_month": r.highlight_of_month,
        "social_post_link_1": r.social_post_link_1,
        "social_post_link_2": r.social_post_link_2,
        "social_post_link_3": r.social_post_link_3,
        "status": r.status.value, "submitted_at": r.submitted_at,
        "total_students": r.total_students, "total_won": r.total_won,
        "reviewed_by": r.reviewed_by, "reviewed_at": r.reviewed_at,
        "review_notes": r.review_notes,
        "reviewer_name": r.reviewer.name if r.reviewer else None,
        "reviewer_role": r.reviewer.role.value if r.reviewer else None,
    }


@router.post("/{report_id}/submit")
def submit_report(
    report_id: int, db: Session = Depends(get_db), current_user=Depends(require_any),
):
    r = db.query(MonthlyReport).filter(MonthlyReport.id == report_id).first()
    if not r: raise HTTPException(404, "Report not found")
    if r.status == ReportStatusEnum.submitted:
        raise HTTPException(400, "Already submitted")
    r.status = ReportStatusEnum.submitted
    r.submitted_at = datetime.utcnow()
    r.submitted_by = current_user.id
    db.commit()
    return {"message": "Report submitted successfully"}


@router.delete("/{report_id}")
def delete_report(
    report_id: int, db: Session = Depends(get_db), current_user=Depends(require_any),
):
    if current_user.role not in (RoleEnum.state_admin, RoleEnum.division_master):
        raise HTTPException(403, "Not authorised to delete reports")
    r = db.query(MonthlyReport).filter(MonthlyReport.id == report_id).first()
    if not r: raise HTTPException(404, "Report not found")
    db.delete(r)
    db.commit()
    return {"message": "Report deleted"}


@router.post("/{report_id}/review")
def review_report(
    report_id: int,
    body: dict = Body(...),
    db: Session = Depends(get_db), current_user=Depends(require_sub_and_above),
):
    if current_user.role not in (RoleEnum.state_admin, RoleEnum.division_master):
        raise HTTPException(403, "Only Division Masters or State Admin can review reports")
    r = db.query(MonthlyReport).filter(MonthlyReport.id == report_id).first()
    if not r:
        raise HTTPException(404, "Report not found")
    if r.status not in (ReportStatusEnum.submitted, ReportStatusEnum.reviewed):
        raise HTTPException(400, "Report must be submitted before it can be reviewed")

    r.status       = ReportStatusEnum.reviewed
    r.reviewed_by  = current_user.id
    r.reviewed_at  = datetime.now(timezone.utc)
    r.review_notes = body.get("review_notes", "").strip() or None

    # ── Build the review message ──
    school_name = r.school.name if r.school else f"School #{r.school_id}"
    month_names = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    period = f"{month_names[r.report_month]} {r.report_year}"
    msg = (f"Your report for {school_name} ({period}) has been reviewed by {current_user.name}."
           + (f" Notes: {r.review_notes}" if r.review_notes else ""))

    # ── Notify the submitter AND every current ATL trainer of this school ──
    # (so the school's trainers see their work was reviewed — deduped by user id)
    recipient_ids = set()
    if r.submitted_by:
        recipient_ids.add(r.submitted_by)
    trainer_links = db.query(SchoolTrainer).filter(
        SchoolTrainer.school_id == r.school_id,
        SchoolTrainer.is_current == True,
    ).all()
    recipient_ids.update(st.user_id for st in trainer_links)

    for uid in recipient_ids:
        db.add(Notification(
            user_id    = uid,
            title      = "Report Reviewed",
            body       = msg,
            notif_type = "report_reviewed",
            link_page  = "history",
        ))

    db.commit()
    db.refresh(r)
    return {
        "id": r.id, "status": r.status.value,
        "reviewed_by": r.reviewed_by, "reviewed_at": r.reviewed_at,
        "review_notes": r.review_notes,
    }


@router.put("/{report_id}")
def update_report(
    report_id: int, body: ReportUpdate,
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    r = db.query(MonthlyReport).filter(MonthlyReport.id == report_id).first()
    if not r: raise HTTPException(404, "Report not found")
    if current_user.role == RoleEnum.atl_trainer and r.status == ReportStatusEnum.submitted:
        raise HTTPException(403, "Cannot edit submitted report")
    if current_user.role == RoleEnum.principal:
        raise HTTPException(403, "Principals cannot edit reports")
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(r, f, v)
    db.commit()
    db.refresh(r)
    return {"id": r.id, "status": r.status.value}
