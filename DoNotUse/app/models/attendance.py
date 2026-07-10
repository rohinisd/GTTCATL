from sqlalchemy import Column, Integer, Boolean, Date, DateTime, Float, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class TrainerAttendance(Base):
    __tablename__ = "trainer_attendance"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    school_id      = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    date           = Column(Date, nullable=False)
    check_in_at    = Column(DateTime(timezone=True))
    check_out_at   = Column(DateTime(timezone=True))
    check_in_lat   = Column(Float)
    check_in_lng   = Column(Float)
    check_out_lat  = Column(Float)
    check_out_lng  = Column(Float)
    check_in_dist  = Column(Float)    # metres from school at check-in
    check_out_dist = Column(Float)    # metres from school at check-out
    in_geofence    = Column(Boolean, default=True)  # within radius at check-in?
    notes          = Column(Text)
    marked_by      = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now())

    user   = relationship("User", foreign_keys=[user_id])
    school = relationship("School")
    marker = relationship("User", foreign_keys=[marked_by])

    __table_args__ = (
        Index("ix_attn_user_date",   "user_id",   "date"),
        Index("ix_attn_school_date", "school_id", "date"),
    )
