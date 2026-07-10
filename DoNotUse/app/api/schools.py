from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.hierarchy import School, SchoolTrainer, SchoolPrincipal
from app.models.users import RoleEnum
from app.core.security import require_any

router = APIRouter()


@router.get("")
def list_schools(
    division_id: Optional[int] = Query(None),
    sub_division_id: Optional[int] = Query(None),
    district: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(100, le=500),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    q = db.query(School).filter(School.is_active == True)
    if current_user.role == RoleEnum.atl_trainer:
        ids = [st.school_id for st in db.query(SchoolTrainer).filter(
            SchoolTrainer.user_id == current_user.id, SchoolTrainer.is_current == True).all()]
        q = q.filter(School.id.in_(ids))
    elif current_user.role == RoleEnum.principal:
        ids = [sp.school_id for sp in db.query(SchoolPrincipal).filter(
            SchoolPrincipal.user_id == current_user.id, SchoolPrincipal.is_current == True).all()]
        q = q.filter(School.id.in_(ids))
    if division_id:     q = q.filter(School.division_id == division_id)
    if sub_division_id: q = q.filter(School.sub_division_id == sub_division_id)
    if district:        q = q.filter(School.district.ilike(f"%{district}%"))
    if search:          q = q.filter(School.name.ilike(f"%{search}%") | School.udise_code.ilike(f"%{search}%"))
    schools = q.order_by(School.name).offset(skip).limit(limit).all()
    return [
        {
            "id": s.id, "udise_code": s.udise_code, "atl_lab_code": s.atl_lab_code,
            "name": s.name, "district": s.district, "pin_code": s.pin_code,
            "division_id": s.division_id, "sub_division_id": s.sub_division_id,
            "school_type": s.school_type.value if s.school_type else None,
            "lab_type": s.lab_type.value if s.lab_type else None,
            "education_type": s.education_type.value if s.education_type else None,
            "max_grade": s.max_grade,
            "principal_name": s.principal_name, "principal_phone": s.principal_phone,
            "lab_area_sqft": s.lab_area_sqft,
            "lab_launch_date": str(s.lab_launch_date) if s.lab_launch_date else None,
            "is_active": s.is_active, "created_at": s.created_at,
        }
        for s in schools
    ]


@router.get("/{school_id}")
def get_school(school_id: int, db: Session = Depends(get_db), _=Depends(require_any)):
    s = db.query(School).filter(School.id == school_id, School.is_active == True).first()
    if not s:
        from fastapi import HTTPException
        raise HTTPException(404, "School not found")
    return {
        "id": s.id, "udise_code": s.udise_code, "atl_lab_code": s.atl_lab_code,
        "name": s.name, "address": s.address, "district": s.district,
        "pin_code": s.pin_code, "state": s.state,
        "division_id": s.division_id, "sub_division_id": s.sub_division_id,
        "school_type": s.school_type.value if s.school_type else None,
        "lab_type": s.lab_type.value if s.lab_type else None,
        "education_type": s.education_type.value if s.education_type else None,
        "max_grade": s.max_grade,
        "principal_name": s.principal_name, "principal_email": s.principal_email,
        "principal_phone": s.principal_phone,
        "lab_incharge_name": s.lab_incharge_name, "lab_incharge_phone": s.lab_incharge_phone,
        "lab_area_sqft": s.lab_area_sqft,
        "lab_launch_date": str(s.lab_launch_date) if s.lab_launch_date else None,
        "lab_photo_1": s.lab_photo_1, "lab_photo_2": s.lab_photo_2, "lab_photo_3": s.lab_photo_3,
        "social_facebook": s.social_facebook, "social_instagram": s.social_instagram,
        "social_twitter": s.social_twitter, "social_youtube": s.social_youtube,
        "is_active": s.is_active, "created_at": s.created_at,
    }
