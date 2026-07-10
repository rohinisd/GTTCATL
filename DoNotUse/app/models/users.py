from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Float, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class RoleEnum(str, enum.Enum):
    state_admin     = "state_admin"
    division_master = "division_master"
    master_trainer  = "master_trainer"
    atl_trainer     = "atl_trainer"
    principal       = "principal"


class GenderEnum(str, enum.Enum):
    male   = "male"
    female = "female"
    other  = "other"


class CasteEnum(str, enum.Enum):
    sc     = "sc"
    st     = "st"
    cat_1  = "cat_1"
    cat_2a = "cat_2a"
    cat_2b = "cat_2b"
    cat_3a = "cat_3a"
    cat_3b = "cat_3b"
    other  = "other"


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action      = Column(String(100), nullable=False)
    model_type  = Column(String(100))
    model_id    = Column(Integer)
    description = Column(String(400))
    changes     = Column(Text)
    ip_address  = Column(String(45))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="activity_logs")

    @classmethod
    def log(cls, db, user_id, action, model_type=None, model_id=None,
            description=None, old_values=None, ip_address=None):
        import json
        entry = cls(
            user_id=user_id,
            action=action,
            model_type=model_type,
            model_id=model_id,
            description=description,
            changes=json.dumps(old_values, default=str) if old_values else None,
            ip_address=ip_address,
        )
        db.add(entry)


class User(Base):
    __tablename__ = "users"

    id                   = Column(Integer, primary_key=True, index=True)
    name                 = Column(String(150), nullable=False)
    email                = Column(String(150), unique=True, nullable=False, index=True)
    phone                = Column(String(15))
    hashed_password      = Column(String(200), nullable=False)
    role                 = Column(Enum(RoleEnum), nullable=False)
    gender               = Column(Enum(GenderEnum))
    caste                = Column(Enum(CasteEnum))
    qualification        = Column(String(200))
    salary               = Column(Float, default=0)      # monthly salary (mainly for atl_trainer)
    districts            = Column(JSON, nullable=True)   # list of district names for master_trainer
    dob                  = Column(Date)
    photo                = Column(String(300))
    division_id          = Column(Integer, ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True)
    sub_division_id      = Column(Integer, ForeignKey("sub_divisions.id", ondelete="SET NULL"), nullable=True)
    is_active            = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=True)
    last_login_at        = Column(DateTime(timezone=True))
    last_login_ip        = Column(String(45))
    created_at           = Column(DateTime(timezone=True), server_default=func.now())
    updated_at           = Column(DateTime(timezone=True), onupdate=func.now())

    division              = relationship("Division", back_populates="users")
    sub_division          = relationship("SubDivision", back_populates="users")
    school_assignments    = relationship("SchoolTrainer", back_populates="user", cascade="all, delete-orphan")
    principal_assignments = relationship("SchoolPrincipal", back_populates="user", cascade="all, delete-orphan")
    submitted_reports     = relationship("MonthlyReport", foreign_keys="MonthlyReport.submitted_by", back_populates="submitter")
    activity_logs         = relationship("ActivityLog", back_populates="user")
