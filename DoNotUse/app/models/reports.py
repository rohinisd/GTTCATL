from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, ForeignKey, Enum, UniqueConstraint, Index, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base
from app.models.users import ActivityLog  # re-export for admin.py compatibility


class ReportStatusEnum(str, enum.Enum):
    draft     = "draft"
    submitted = "submitted"
    reviewed  = "reviewed"


class MonthlyReport(Base):
    __tablename__ = "monthly_reports"

    id            = Column(Integer, primary_key=True, index=True)
    school_id     = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    submitted_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    report_year   = Column(Integer, nullable=False)
    report_month  = Column(Integer, nullable=False)
    academic_year = Column(String(10), nullable=False)

    students_school                 = Column(Integer, default=0)
    students_community              = Column(Integer, default=0)
    students_girls                  = Column(Integer, default=0)
    workshops_school                = Column(Integer, default=0)
    workshops_community             = Column(Integer, default=0)
    mentoring_school                = Column(Integer, default=0)
    mentoring_community             = Column(Integer, default=0)
    innovation_school               = Column(Integer, default=0)
    innovation_community            = Column(Integer, default=0)
    patents_school                  = Column(Integer, default=0)
    patents_community               = Column(Integer, default=0)
    copyrights_school               = Column(Integer, default=0)
    copyrights_community            = Column(Integer, default=0)
    atl_competitions_participated   = Column(Integer, default=0)
    atl_competitions_won            = Column(Integer, default=0)
    other_competitions_participated = Column(Integer, default=0)
    other_competitions_won          = Column(Integer, default=0)
    industrial_visits               = Column(Integer, default=0)
    ip_granted                      = Column(Integer, default=0)   # Patents/Copyrights granted this month (combined)
    ip_filed                        = Column(Integer, default=0)   # Patents/Copyrights filed this month (combined)
    highlight_of_month              = Column(Text)
    social_post_link_1              = Column(String(300))
    social_post_link_2              = Column(String(300))
    social_post_link_3              = Column(String(300))

    status       = Column(Enum(ReportStatusEnum), default=ReportStatusEnum.draft)
    submitted_at = Column(DateTime(timezone=True))
    reviewed_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at  = Column(DateTime(timezone=True))
    review_notes = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())

    school    = relationship("School", back_populates="monthly_reports")
    submitter = relationship("User", foreign_keys=[submitted_by], back_populates="submitted_reports")
    reviewer  = relationship("User", foreign_keys=[reviewed_by])

    __table_args__ = (
        UniqueConstraint("school_id", "report_year", "report_month", name="uq_school_period"),
        Index("ix_report_year_month", "report_year", "report_month"),
    )

    @property
    def total_students(self):
        return (self.students_school or 0) + (self.students_community or 0)

    @property
    def total_won(self):
        return (self.atl_competitions_won or 0) + (self.other_competitions_won or 0)

    # ── Backward-compat computed totals ───────────────────
    @property
    def workshops_count(self):
        return (self.workshops_school or 0) + (self.workshops_community or 0)

    @property
    def mentoring_sessions(self):
        return (self.mentoring_school or 0) + (self.mentoring_community or 0)

    @property
    def innovation_projects(self):
        return (self.innovation_school or 0) + (self.innovation_community or 0)

    @property
    def patents_filed(self):
        return (self.patents_school or 0) + (self.patents_community or 0)

    @property
    def copyrights_filed(self):
        return (self.copyrights_school or 0) + (self.copyrights_community or 0)


class BulkUpload(Base):
    __tablename__ = "bulk_uploads"

    id           = Column(Integer, primary_key=True, index=True)
    uploaded_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    file_name    = Column(String(200))
    record_type  = Column(String(50))
    total_rows   = Column(Integer, default=0)
    success_rows = Column(Integer, default=0)
    failed_rows  = Column(Integer, default=0)
    error_log    = Column(Text)
    status       = Column(String(20), default="pending")
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


class GalleryImage(Base):
    __tablename__ = "gallery_images"

    id          = Column(Integer, primary_key=True, index=True)
    school_id   = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    report_id   = Column(Integer, ForeignKey("monthly_reports.id", ondelete="SET NULL"), nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    image_url   = Column(String(400), nullable=False)
    title       = Column(String(200))
    description = Column(Text)
    category    = Column(String(40), default="lab")   # industrial_visit | group | lab
    report_year  = Column(Integer)
    report_month = Column(Integer)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    school   = relationship("School")
    uploader = relationship("User", foreign_keys=[uploaded_by])


class ATLCompetition(Base):
    __tablename__ = "atl_competitions"

    id                        = Column(Integer, primary_key=True, index=True)
    competition_date          = Column(Date, nullable=False)
    venue_school              = Column(String(200))
    sub_district              = Column(String(100))
    division_id               = Column(Integer, ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True)
    atl_teams_participated    = Column(Integer, default=0)
    other_teams_participated  = Column(Integer, default=0)
    atl_teams_not_participated= Column(Integer, default=0)
    atl_teams_won             = Column(Integer, default=0)
    others_won                = Column(Integer, default=0)
    submitted_by              = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at                = Column(DateTime(timezone=True), server_default=func.now())

    division  = relationship("Division")
    submitter = relationship("User", foreign_keys=[submitted_by])


class Notification(Base):
    __tablename__ = "notifications"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title       = Column(String(200), nullable=False)
    body        = Column(String(500))
    notif_type  = Column(String(50))   # pending_report | report_reviewed | competition_added | reminder_sent
    link_page   = Column(String(50))   # which page to navigate to on click
    is_read     = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id            = Column(Integer, primary_key=True, index=True)
    title         = Column(String(200), nullable=False)
    description   = Column(Text)
    event_date    = Column(Date, nullable=False)
    end_date      = Column(Date)
    event_type    = Column(String(50), default="event")  # competition | training | deadline | event
    division_id   = Column(Integer, ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True)
    is_all_divisions = Column(Boolean, default=True)
    created_by    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    division = relationship("Division")
    creator  = relationship("User", foreign_keys=[created_by])


class EquipmentInventory(Base):
    __tablename__ = "equipment_inventory"

    id            = Column(Integer, primary_key=True, index=True)
    school_id     = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    item_name     = Column(String(200), nullable=False)
    quantity      = Column(Integer, default=1)           # total issued / in stock
    condition     = Column(String(20), default="good")   # good | damaged | missing
    last_checked  = Column(Date)
    notes         = Column(Text)
    added_by      = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # ── issuance (set by SPD / state admin) ──
    issued_by     = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    issued_at     = Column(DateTime(timezone=True))
    # ── condition review (set by the school's ATL trainer) ──
    working_qty         = Column(Integer)
    not_working_qty     = Column(Integer)
    additional_required = Column(Integer)
    review_notes        = Column(Text)
    reviewed_by         = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at         = Column(DateTime(timezone=True))
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

    school   = relationship("School")
    adder    = relationship("User", foreign_keys=[added_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])


class DivisionTarget(Base):
    __tablename__ = "division_targets"

    id                = Column(Integer, primary_key=True, index=True)
    division_id       = Column(Integer, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    academic_year     = Column(String(10), nullable=False)
    target_students   = Column(Integer, default=0)
    target_workshops  = Column(Integer, default=0)
    target_projects   = Column(Integer, default=0)
    target_wins       = Column(Integer, default=0)
    target_industrial = Column(Integer, default=0)
    target_atl_comp    = Column(Integer, default=0)
    target_other_comp  = Column(Integer, default=0)
    target_mentoring   = Column(Integer, default=0)
    target_exhibitions = Column(Integer, default=0)
    created_by        = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), onupdate=func.now())

    division = relationship("Division")
    creator  = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("division_id", "academic_year", name="uq_div_target_year"),
    )


class InventoryRequest(Base):
    """Trainer requests inventory from GTTC; SPD approves/rejects/fulfills.
    Adapted to the flat equipment_inventory table — no separate items catalog."""
    __tablename__ = "inventory_requests"

    id               = Column(Integer, primary_key=True, index=True)
    school_id        = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    # Optional ref to the school's existing equipment row (for "request more")
    item_id          = Column(Integer, ForeignKey("equipment_inventory.id", ondelete="SET NULL"), nullable=True)
    item_name        = Column(String(200), nullable=False)   # always present
    item_desc        = Column(Text)                          # extra context for new items
    is_new_item      = Column(Boolean, default=False)        # true = not yet in school's inventory
    requested_qty    = Column(Integer, nullable=False)
    approved_qty     = Column(Integer)
    reason           = Column(Text, nullable=False)
    urgency          = Column(String(10), default="medium")  # low | medium | high
    status           = Column(String(20), default="pending") # pending | approved | rejected | fulfilled
    rejection_reason = Column(Text)
    requested_by     = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by      = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at      = Column(DateTime(timezone=True))
    fulfilled_at     = Column(DateTime(timezone=True))
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), onupdate=func.now())

    school    = relationship("School")
    item      = relationship("EquipmentInventory", foreign_keys=[item_id])
    requester = relationship("User", foreign_keys=[requested_by])
    reviewer  = relationship("User", foreign_keys=[reviewed_by])

    __table_args__ = (
        Index("ix_invreq_school_status", "school_id", "status"),
        Index("ix_invreq_status_urgency", "status", "urgency"),
    )


class Project(Base):
    """An experiment/project the SPD wants schools to complete (e.g. from the
    ATL experiment list). Each has a bill-of-materials (ProjectItem rows).
    SPD activates the ones to run this month; ATL trainers then select the
    projects they completed in their monthly report."""
    __tablename__ = "projects"

    id            = Column(Integer, primary_key=True, index=True)
    exp_no        = Column(Integer)                       # experiment number (1..40)
    name          = Column(String(300), nullable=False)
    description   = Column(Text)
    is_active     = Column(Boolean, default=True)         # visible to trainers for selection
    target_year   = Column(Integer)                       # optional: month this project is planned for
    target_month  = Column(Integer)
    academic_year = Column(String(10))
    created_by    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

    items = relationship("ProjectItem", back_populates="project", cascade="all, delete-orphan")


class ProjectItem(Base):
    """One line of a project's bill-of-materials: an item + quantity needed."""
    __tablename__ = "project_items"

    id         = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    item_name  = Column(String(200), nullable=False)
    quantity   = Column(String(40))      # as written: "1", "4", "As required", "1 Set", "33-36"
    qty_num    = Column(Integer)         # parsed numeric qty for usage maths (null if non-numeric)

    project = relationship("Project", back_populates="items")

    __table_args__ = (Index("ix_projitem_name", "item_name"),)


class ReportProjectUsage(Base):
    """Links a submitted monthly report to the projects the trainer selected.
    Item usage = sum of each linked project's BOM quantities across all reports."""
    __tablename__ = "report_project_usage"

    id         = Column(Integer, primary_key=True, index=True)
    report_id  = Column(Integer, ForeignKey("monthly_reports.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    school_id  = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("report_id", "project_id", name="uq_report_project"),
        Index("ix_rpu_project", "project_id"),
    )


class ReportUsedItem(Base):
    """Items the ATL trainer reports as used during the month."""
    __tablename__ = "report_used_items"

    id          = Column(Integer, primary_key=True, index=True)
    report_id   = Column(Integer, ForeignKey("monthly_reports.id", ondelete="CASCADE"), nullable=False)
    school_id   = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True)
    item_name   = Column(String(200), nullable=False)
    quantity    = Column(Integer, nullable=False, default=1)   # units used per session
    usage_count = Column(Integer, nullable=False, default=1)   # total times used this month
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_rui_report", "report_id"),)


class ReportBrokenItem(Base):
    """Items the ATL trainer reports as broken/damaged during the month."""
    __tablename__ = "report_broken_items"

    id         = Column(Integer, primary_key=True, index=True)
    report_id  = Column(Integer, ForeignKey("monthly_reports.id", ondelete="CASCADE"), nullable=False)
    school_id  = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True)
    item_name  = Column(String(200), nullable=False)
    quantity   = Column(Integer, nullable=False, default=1)
    reason     = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_rbi_report", "report_id"),)


class SystemSetting(Base):
    """Simple key/value store for global portal settings (e.g. the current
    academic year that drives every dashboard's cards, charts and tables)."""
    __tablename__ = "system_settings"

    key        = Column(String(50), primary_key=True)
    value      = Column(String(200))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EquipmentInspection(Base):
    """First-time (or periodic) equipment inspection submitted by an ATL trainer
    when assigned to a new school.  Captures the physical state of every item
    against what is recorded in the school register."""
    __tablename__ = "equipment_inspections"

    id              = Column(Integer, primary_key=True, index=True)
    school_id       = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    inspection_date = Column(Date, nullable=False)
    notes           = Column(Text)
    submitted_by    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    school    = relationship("School")
    submitter = relationship("User", foreign_keys=[submitted_by])
    items     = relationship("InspectionItem", back_populates="inspection", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_inspection_school", "school_id"),)


class InspectionItem(Base):
    """One equipment line inside an EquipmentInspection."""
    __tablename__ = "inspection_items"

    id                  = Column(Integer, primary_key=True, index=True)
    inspection_id       = Column(Integer, ForeignKey("equipment_inspections.id", ondelete="CASCADE"), nullable=False)
    item_name           = Column(String(200), nullable=False)
    stock_in_register   = Column(Integer, default=0)   # as per school register
    currently_available = Column(Integer, default=0)   # physically present
    working             = Column(Integer, default=0)
    not_working         = Column(Integer, default=0)
    missing             = Column(Integer, default=0)   # stock_in_register - currently_available

    inspection = relationship("EquipmentInspection", back_populates="items")

    __table_args__ = (Index("ix_inspitem_inspection", "inspection_id"),)
