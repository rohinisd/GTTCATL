from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.users import User
from app.schemas.user_schema import UserUpdate
from app.core.security import get_current_user, verify_password, hash_password

router = APIRouter()


@router.get("/me")
def get_profile(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "phone": current_user.phone,
        "role": current_user.role.value,
        "gender": current_user.gender.value if current_user.gender else None,
        "caste": current_user.caste.value if current_user.caste else None,
        "dob": str(current_user.dob) if current_user.dob else None,
        "photo": current_user.photo,
        "division_id": current_user.division_id,
        "sub_division_id": current_user.sub_division_id,
        "must_change_password": current_user.must_change_password,
        "last_login_at": current_user.last_login_at,
        "created_at": current_user.created_at,
    }


@router.put("/me")
def update_profile(
    body: UserUpdate,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    for field, val in body.dict(exclude_none=True).items():
        setattr(current_user, field, val)
    db.commit()
    db.refresh(current_user)
    return {"id": current_user.id, "name": current_user.name}


@router.post("/me/change-password")
def change_password(
    old_password: str, new_password: str,
    db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    if not verify_password(old_password, current_user.hashed_password):
        raise HTTPException(400, "Old password is incorrect")
    if len(new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    current_user.hashed_password = hash_password(new_password)
    current_user.must_change_password = False
    db.commit()
    return {"message": "Password changed successfully"}
