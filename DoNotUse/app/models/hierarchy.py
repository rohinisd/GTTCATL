from sqlalchemy import Column, Integer, String, Boolean, Date, Float, Text, ForeignKey, Index, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import DateTime
import enum
from app.database import Base


class LabTypeEnum(str, enum.Enum):
    atl = "atl"
    stl = "stl"


class SchoolTypeEnum(str, enum.Enum):
    government = "government"
    aided      = "aided"
    private    = "private"
    central    = "central"


class EducationTypeEnum(str, enum.Enum):
    primary          = "primary"
    upper_primary    = "upper_primary"
    secondary        = "secondary"
    higher_secondary = "higher_secondary"
    composite        = "composite"
    co_education     = "co_education"
    non_co_education = "non_co_education"


class Division(Base):
    __tablename__ = "divisions"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(100), nullable=False)
    code       = Column(String(20), unique=True, nullable=False)
    state      = Column(String(100), default="Karnataka")
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sub_divisions = relationship("SubDivision", back_populates="division", cascade="all, delete-orphan")
    schools       = relationship("School", back_populates="division", cascade="all, delete-orphan")
    users         = relationship("User", back_populates="division")


class SubDivision(Base):
    __tablename__ = "sub_divisions"

    id          = Column(Integer, primary_key=True, index=True)
    division_id = Column(Integer, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    name        = Column(String(100), nullable=False)
    code        = Column(String(20), unique=True, nullable=False)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    division = relationship("Division", back_populates="sub_divisions")
    schools  = relationship("School", back_populates="sub_division", cascade="all, delete-orphan")
    users    = relationship("User", back_populates="sub_division")


class School(Base):
    __tablename__ = "schools"

    id               = Column(Integer, primary_key=True, index=True)
    udise_code       = Column(String(20), unique=True, nullable=False, index=True)
    atl_lab_code     = Column(String(30), unique=True, nullable=True)
    pin_code         = Column(String(10), nullable=False)
    name             = Column(String(200), nullable=False)
    address          = Column(Text)
    district         = Column(String(100), nullable=False)
    state            = Column(String(100), default="Karnataka")
    division_id      = Column(Integer, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    sub_division_id  = Column(Integer, ForeignKey("sub_divisions.id", ondelete="SET NULL"), nullable=True)
    school_type      = Column(Enum(SchoolTypeEnum), default=SchoolTypeEnum.government)
    lab_type         = Column(Enum(LabTypeEnum), default=LabTypeEnum.atl)
    education_type   = Column(Enum(EducationTypeEnum), default=EducationTypeEnum.secondary)
    max_grade        = Column(Integer, default=10)
    contact_no       = Column(String(20))
    school_email     = Column(String(150))
    principal_name   = Column(String(150))
    principal_email  = Column(String(150))
    principal_phone  = Column(String(15))
    lab_incharge_name  = Column(String(150))
    lab_incharge_email = Column(String(150))
    lab_incharge_phone = Column(String(15))
    lab_area_sqft    = Column(Integer)
    lab_launch_date  = Column(Date)
    lab_photo_1      = Column(String(300))
    lab_photo_2      = Column(String(300))
    lab_photo_3      = Column(String(300))
    social_facebook  = Column(String(300))
    social_instagram = Column(String(300))
    social_twitter   = Column(String(300))
    social_youtube   = Column(String(300))
    social_gttc_clicks = Column(String(300))
    geo_latitude     = Column(Float)
    geo_longitude    = Column(Float)
    geo_radius       = Column(Integer, default=200)   # metres
    school_start_time = Column(String(5))   # "HH:MM" e.g. "09:00"
    school_end_time   = Column(String(5))   # "HH:MM" e.g. "17:00"
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), onupdate=func.now())

    division        = relationship("Division", back_populates="schools")
    sub_division    = relationship("SubDivision", back_populates="schools")
    trainer_links   = relationship("SchoolTrainer", back_populates="school", cascade="all, delete-orphan")
    principal_links = relationship("SchoolPrincipal", back_populates="school", cascade="all, delete-orphan")
    monthly_reports = relationship("MonthlyReport", back_populates="school", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_school_div", "division_id"),
    )


class SchoolTrainer(Base):
    __tablename__ = "school_trainers"

    id            = Column(Integer, primary_key=True, index=True)
    school_id     = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_from = Column(Date, nullable=False)
    assigned_to   = Column(Date)
    is_current    = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    school = relationship("School", back_populates="trainer_links")
    user   = relationship("User", back_populates="school_assignments")


class SchoolPrincipal(Base):
    __tablename__ = "school_principals"

    id            = Column(Integer, primary_key=True, index=True)
    school_id     = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_from = Column(Date, nullable=False)
    assigned_to   = Column(Date)
    is_current    = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    school = relationship("School", back_populates="principal_links")
    user   = relationship("User", back_populates="principal_assignments")
