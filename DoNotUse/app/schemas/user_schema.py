from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date
from app.models.users import RoleEnum, GenderEnum, CasteEnum


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    password: str
    role: RoleEnum
    gender: Optional[GenderEnum] = None
    caste: Optional[CasteEnum] = None
    qualification: Optional[str] = None
    salary: Optional[float] = None
    districts: Optional[List[str]] = None   # for master_trainer: list of district names
    dob: Optional[date] = None
    division_id: Optional[int] = None
    sub_division_id: Optional[int] = None
    school_id: Optional[int] = None   # for atl_trainer: assigns SchoolTrainer link


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[GenderEnum] = None
    caste: Optional[CasteEnum] = None
    qualification: Optional[str] = None
    salary: Optional[float] = None
    dob: Optional[date] = None
    photo: Optional[str] = None
    is_active: Optional[bool] = None
    division_id: Optional[int] = None
    sub_division_id: Optional[int] = None


class SchoolCreate(BaseModel):
    # Required
    udise_code: str
    atl_lab_code: str
    pin_code: str
    name: str
    district: str
    division_id: int
    sub_division_id: Optional[int] = None
    school_type: str = "government"
    lab_type: str = "atl"
    # Optional school info
    contact_no: Optional[str] = None
    school_email: Optional[str] = None
    state: str = "Karnataka"
    address: Optional[str] = None
    education_type: Optional[str] = None
    max_grade: Optional[int] = None
    principal_name: Optional[str] = None
    principal_email: Optional[str] = None
    principal_phone: Optional[str] = None
    lab_incharge_name: Optional[str] = None
    lab_incharge_email: Optional[str] = None
    lab_incharge_phone: Optional[str] = None
    lab_area_sqft: Optional[int] = None
    lab_launch_date: Optional[date] = None
    social_facebook: Optional[str] = None
    social_youtube: Optional[str] = None
    social_gttc_clicks: Optional[str] = None
    geo_latitude: Optional[float] = None
    geo_longitude: Optional[float] = None
    geo_radius: Optional[int] = None
    school_start_time: Optional[str] = None   # "HH:MM"
    school_end_time:   Optional[str] = None   # "HH:MM"
    # Trainer info — required
    trainer_name: str
    trainer_email: str
    trainer_phone: str
    trainer_gender: GenderEnum
    trainer_caste: CasteEnum
    trainer_dob: Optional[date] = None
    trainer_salary: Optional[float] = None


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    contact_no: Optional[str] = None
    school_email: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    pin_code: Optional[str] = None
    school_type: Optional[str] = None
    lab_type: Optional[str] = None
    education_type: Optional[str] = None
    max_grade: Optional[int] = None
    principal_name: Optional[str] = None
    principal_email: Optional[str] = None
    principal_phone: Optional[str] = None
    lab_incharge_name: Optional[str] = None
    lab_incharge_email: Optional[str] = None
    lab_incharge_phone: Optional[str] = None
    lab_area_sqft: Optional[int] = None
    lab_launch_date: Optional[date] = None
    lab_photo_1: Optional[str] = None
    lab_photo_2: Optional[str] = None
    lab_photo_3: Optional[str] = None
    social_facebook: Optional[str] = None
    social_instagram: Optional[str] = None
    social_twitter: Optional[str] = None
    social_youtube: Optional[str] = None
    social_gttc_clicks: Optional[str] = None
    geo_latitude: Optional[float] = None
    geo_longitude: Optional[float] = None
    geo_radius: Optional[int] = None
    school_start_time: Optional[str] = None   # "HH:MM"
    school_end_time:   Optional[str] = None   # "HH:MM"
