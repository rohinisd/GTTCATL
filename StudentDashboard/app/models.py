from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    email = Column(String(180), unique=True, index=True, nullable=False)
    hashed_password = Column(String(240), nullable=False)
    role = Column(String(80), default="student")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Trainer(Base):
    __tablename__ = "trainers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    email = Column(String(180), unique=True, index=True, nullable=False)
    phone = Column(String(40))
    specialization = Column(String(160))
    role = Column(String(80), default="atl_trainer")
    gender = Column(String(40))
    caste = Column(String(40))
    division = Column(String(120))
    districts = Column(Text)
    assigned_school = Column(String(220))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(220), nullable=False)
    udise_code = Column(String(40), unique=True, index=True)
    atl_lab_code = Column(String(60), unique=True, index=True)
    district = Column(String(120))
    division = Column(String(120))
    state = Column(String(120), default="Karnataka")
    pin_code = Column(String(20))
    school_type = Column(String(80), default="government")
    lab_type = Column(String(80), default="atl")
    education_type = Column(String(80), default="secondary")
    max_grade = Column(Integer, default=10)
    principal_name = Column(String(160))
    principal_email = Column(String(180))
    principal_phone = Column(String(40))
    lab_area_sqft = Column(Integer)
    lab_launch_date = Column(Date)
    assigned_trainer = Column(String(160))
    current_students = Column(Integer, default=0)
    girls_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    students = relationship("Student", back_populates="school")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    email = Column(String(180), unique=True, index=True)
    grade = Column(String(40))
    father_name = Column(String(160))
    mother_name = Column(String(160))
    age = Column(Integer)
    gender = Column(String(40))
    caste = Column(String(80))
    category = Column(String(80))
    phone = Column(String(40))
    urban_rural = Column(String(40))
    income_status = Column(String(20))
    physically_challenged = Column(String(10))
    medium = Column(String(80))
    state = Column(String(120))
    district = Column(String(120))
    taluk = Column(String(120))
    village = Column(String(160))
    pincode = Column(String(20))
    address = Column(Text)
    school_id = Column(Integer, ForeignKey("schools.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    school = relationship("School", back_populates="students")
    enrollments = relationship("Enrollment", back_populates="student")
    attendance_records = relationship("AttendanceRecord", back_populates="student")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(220), nullable=False)
    description = Column(Text)
    level = Column(String(80))
    sector = Column(String(160))
    sub_sector = Column(String(160))
    occupation = Column(String(160))
    reference_id = Column(String(120))
    resource_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lessons = relationship("Lesson", back_populates="course")
    enrollments = relationship("Enrollment", back_populates="course")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    status = Column(String(40), default="assigned")
    progress = Column(Integer, default=0)
    assigned_by = Column(String(160))
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    student = relationship("Student", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(220), nullable=False)
    content_type = Column(String(80), default="article")
    content_body = Column(Text)
    resource_url = Column(String(500))
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    course = relationship("Course", back_populates="lessons")
    resources = relationship("LessonResource", back_populates="lesson")


class LessonResource(Base):
    __tablename__ = "lesson_resources"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    title = Column(String(220), nullable=False)
    content_type = Column(String(80), default="article")
    content_body = Column(Text)
    resource_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lesson = relationship("Lesson", back_populates="resources")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    name = Column(String(160), nullable=False)
    trainer_name = Column(String(160))
    schedule = Column(String(160))
    start_date = Column(Date)
    end_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    school = relationship("School")
    attendance_records = relationship("AttendanceRecord", back_populates="batch")
    performance_assessment = relationship("BatchPerformanceAssessment", back_populates="batch")
    teamwork_badges = relationship("StudentTeamworkBadge", back_populates="batch")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    attendance_date = Column(Date, nullable=False)
    status = Column(String(40), default="present")
    remarks = Column(Text)
    marked_by = Column(String(160))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    batch = relationship("Batch", back_populates="attendance_records")
    student = relationship("Student", back_populates="attendance_records")


class BatchPerformanceAssessment(Base):
    __tablename__ = "batch_performance_assessments"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False, unique=True)
    concept_understanding = Column(String(40), default="not_assessed")
    project_understanding = Column(String(40), default="not_assessed")
    design_thinking = Column(String(40), default="not_assessed")
    assessed_by = Column(String(160))
    remarks = Column(Text)
    assessed_at = Column(DateTime(timezone=True), server_default=func.now())

    batch = relationship("Batch", back_populates="performance_assessment")


class StudentTeamworkBadge(Base):
    __tablename__ = "student_teamwork_badges"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    badge = Column(String(40), nullable=False)
    assigned_by = Column(String(160))
    remarks = Column(Text)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())

    batch = relationship("Batch", back_populates="teamwork_badges")
    student = relationship("Student")


class AtlForm(Base):
    __tablename__ = "atl_forms"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(40))
    title = Column(String(220), nullable=False)
    filename = Column(String(220), nullable=False)
    stored_name = Column(String(220), nullable=False)
    uploaded_by = Column(String(160))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
