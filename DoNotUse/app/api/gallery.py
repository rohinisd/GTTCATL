import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import require_any
from app.models.reports import GalleryImage
from app.models.users import RoleEnum
from app.models.hierarchy import School, SchoolTrainer, SchoolPrincipal
from app.services.aggregator import get_scoped_schools

router = APIRouter()

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_SIZE = 8 * 1024 * 1024  # 8 MB
UPLOAD_DIR = "app/static/uploads"
VALID_CATEGORIES = {"industrial_visit", "group", "lab", "competition", "innovation_project"}


def _user_school_id(db: Session, current_user) -> Optional[int]:
    """Resolve the school a trainer/principal belongs to."""
    if current_user.role == RoleEnum.atl_trainer:
        link = db.query(SchoolTrainer).filter(
            SchoolTrainer.user_id == current_user.id,
            SchoolTrainer.is_current == True,
        ).first()
        return link.school_id if link else None
    if current_user.role == RoleEnum.principal:
        link = db.query(SchoolPrincipal).filter(
            SchoolPrincipal.user_id == current_user.id,
            SchoolPrincipal.is_current == True,
        ).first()
        return link.school_id if link else None
    return None


@router.post("/upload")
async def upload_gallery_image(
    file: UploadFile = File(...),
    category: str = Form("lab"),
    title: str = Form(""),
    description: str = Form(""),
    school_id: Optional[int] = Form(None),
    report_id: Optional[int] = Form(None),
    report_year: Optional[int] = Form(None),
    report_month: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_any),
):
    if current_user.role == RoleEnum.principal:
        raise HTTPException(403, "Principals have read-only access")

    category = category if category in VALID_CATEGORIES else "lab"

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"File type not allowed. Use: {', '.join(sorted(ALLOWED_EXT))}")

    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(400, "File too large. Maximum size is 8 MB")

    # Resolve the school this image belongs to
    sid = _user_school_id(db, current_user)
    if sid is None:
        sid = school_id
    if sid is None:
        raise HTTPException(400, "school_id required")
    if not db.query(School).filter(School.id == sid).first():
        raise HTTPException(404, "School not found")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    fname = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
        f.write(contents)
    url = f"/static/uploads/{fname}"

    img = GalleryImage(
        school_id=sid, report_id=report_id, uploaded_by=current_user.id,
        image_url=url, title=(title or "").strip()[:200],
        description=(description or "").strip(),
        category=category, report_year=report_year, report_month=report_month,
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    return _serialize(img)


@router.get("")
def list_gallery(
    category: Optional[str] = Query(None),
    school_id: Optional[int] = Query(None),
    report_year: Optional[int] = Query(None),
    report_month: Optional[int] = Query(None),
    division_id: Optional[int] = Query(None),
    district: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(200, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(require_any),
):
    school_q = get_scoped_schools(db, current_user)
    if division_id is not None:
        school_q = school_q.filter(School.division_id == division_id)
    if district:
        school_q = school_q.filter(School.district.ilike(f"%{district}%"))
    scoped_ids = [s.id for s in school_q.all()]
    q = db.query(GalleryImage).filter(GalleryImage.school_id.in_(scoped_ids))
    if category in VALID_CATEGORIES:
        q = q.filter(GalleryImage.category == category)
    if school_id:
        q = q.filter(GalleryImage.school_id == school_id)
    if report_year:
        q = q.filter(GalleryImage.report_year == report_year)
    if report_month:
        q = q.filter(GalleryImage.report_month == report_month)
    if search:
        q = q.join(School, GalleryImage.school_id == School.id).filter(
            School.name.ilike(f"%{search}%") |
            School.district.ilike(f"%{search}%") |
            GalleryImage.title.ilike(f"%{search}%") |
            GalleryImage.description.ilike(f"%{search}%")
        )
    rows = q.order_by(GalleryImage.created_at.desc()).limit(limit).all()
    return [_serialize(r) for r in rows]


@router.delete("/{image_id}")
def delete_gallery_image(
    image_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_any),
):
    img = db.query(GalleryImage).filter(GalleryImage.id == image_id).first()
    if not img:
        raise HTTPException(404, "Image not found")
    # Uploader, or admin/division can delete
    is_admin = current_user.role in (RoleEnum.state_admin, RoleEnum.division_master)
    if img.uploaded_by != current_user.id and not is_admin:
        raise HTTPException(403, "Not allowed to delete this image")
    # Best-effort remove the file
    try:
        path = os.path.join("app", img.image_url.lstrip("/").replace("static/", "static/", 1))
        local = img.image_url.replace("/static/", "app/static/", 1)
        if os.path.exists(local):
            os.remove(local)
    except Exception:
        pass
    db.delete(img)
    db.commit()
    return {"message": "deleted"}


def _serialize(img: GalleryImage):
    return {
        "id": img.id,
        "school_id": img.school_id,
        "school_name": img.school.name if img.school else None,
        "district": img.school.district if img.school else None,
        "division_id": img.school.division_id if img.school else None,
        "division_name": img.school.division.name if img.school and img.school.division else None,
        "image_url": img.image_url,
        "title": img.title,
        "description": img.description,
        "category": img.category,
        "report_year": img.report_year,
        "report_month": img.report_month,
        "uploaded_by": img.uploaded_by,
        "uploader_name": img.uploader.name if img.uploader else None,
        "created_at": img.created_at,
    }
