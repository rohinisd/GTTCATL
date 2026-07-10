from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.users import User
from app.core.security import (
    verify_password, hash_password, create_access_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter()


class ProfileUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    gender: str | None = None
    caste: str | None = None
    dob: str | None = None      # ISO date string YYYY-MM-DD
    photo: str | None = None    # URL / file path


class ChangePassword(BaseModel):
    current_password: str
    new_password: str


@router.post("/token")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    from datetime import datetime, timezone
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = request.client.host if request.client else None
    db.commit()

    token = create_access_token(
        {"sub": str(user.id)},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role.value,
        "name": user.name,
        "must_change_password": user.must_change_password,
    }


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "phone": current_user.phone,
        "role": current_user.role.value,
        "division_id": current_user.division_id,
        "districts": current_user.districts or [],
        "must_change_password": current_user.must_change_password,
    }


@router.put("/me")
def update_me(
    body: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from datetime import date
    if body.name:   current_user.name   = body.name.strip()
    if body.email:  current_user.email  = body.email.strip()
    if body.phone  is not None: current_user.phone  = body.phone.strip()  or None
    if body.gender is not None: current_user.gender = body.gender or None
    if body.caste  is not None: current_user.caste  = body.caste  or None
    if body.photo  is not None: current_user.photo  = body.photo  or None
    if body.dob:
        try:    current_user.dob = date.fromisoformat(body.dob)
        except: pass
    db.commit()
    return {"message": "Profile updated"}


@router.post("/change-password")
def change_password(
    body: ChangePassword,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    current_user.hashed_password = hash_password(body.new_password)
    current_user.must_change_password = False
    db.commit()
    return {"message": "Password changed successfully"}
