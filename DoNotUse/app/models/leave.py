from sqlalchemy import Column, Integer, String, Date, DateTime, Float, Text, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class LeaveStatusEnum(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    from_date   = Column(Date, nullable=False)
    to_date     = Column(Date, nullable=False)
    reason      = Column(Text)
    status      = Column(Enum(LeaveStatusEnum), default=LeaveStatusEnum.pending, nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    review_note = Column(Text)
    reviewed_at = Column(DateTime(timezone=True))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    user     = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    __table_args__ = (
        Index("ix_leave_user", "user_id"),
        Index("ix_leave_status", "status"),
    )


class Holiday(Base):
    __tablename__ = "holidays"

    id          = Column(Integer, primary_key=True, index=True)
    date        = Column(Date, nullable=False)
    name        = Column(String(200), nullable=False)
    # null division_id => applies to every division (state-wide holiday)
    division_id = Column(Integer, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=True)
    created_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    division = relationship("Division")
    creator  = relationship("User")

    __table_args__ = (
        Index("ix_holiday_date", "date"),
    )


class PayrollAdjustment(Base):
    """Manual override applied on top of the calculated payable for a trainer-month."""
    __tablename__ = "payroll_adjustments"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    year        = Column(Integer, nullable=False)
    month       = Column(Integer, nullable=False)
    adjustment  = Column(Float, default=0)   # positive = add, negative = deduct
    remarks     = Column(Text, nullable=False)
    adjusted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    user     = relationship("User", foreign_keys=[user_id])
    adjuster = relationship("User", foreign_keys=[adjusted_by])

    __table_args__ = (
        Index("ix_payroll_adj_user_month", "user_id", "year", "month", unique=True),
    )
