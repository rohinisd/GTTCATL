import os
import re
import secrets
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode, urlparse

import bcrypt
import openpyxl
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, inspect, text

from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401 - registers SQLAlchemy models
from app.content_seed import seed_lms_content
from app.curriculum_import import seed_curriculum_content
from app.handbook_import import VOLUME_COURSES, seed_handbook_volume_courses
from app.seed import seed_initial_data


APP_DIR = Path(__file__).resolve().parent

Base.metadata.create_all(bind=engine)


def _ensure_columns():
    inspector = inspect(engine)

    def add_missing(table_name, columns):
        try:
            existing = {column["name"] for column in inspector.get_columns(table_name)}
        except Exception:
            return

        with engine.begin() as connection:
            for name, definition in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {definition}"))

    add_missing(
        "trainers",
        {
            "role": "VARCHAR(80) DEFAULT 'atl_trainer'",
            "gender": "VARCHAR(40)",
            "caste": "VARCHAR(40)",
            "division": "VARCHAR(120)",
            "districts": "TEXT",
            "assigned_school": "VARCHAR(220)",
        },
    )
    add_missing(
        "schools",
        {
            "atl_lab_code": "VARCHAR(60)",
            "state": "VARCHAR(120) DEFAULT 'Karnataka'",
            "pin_code": "VARCHAR(20)",
            "school_type": "VARCHAR(80) DEFAULT 'government'",
            "lab_type": "VARCHAR(80) DEFAULT 'atl'",
            "education_type": "VARCHAR(80) DEFAULT 'secondary'",
            "max_grade": "INTEGER DEFAULT 10",
            "principal_name": "VARCHAR(160)",
            "principal_email": "VARCHAR(180)",
            "principal_phone": "VARCHAR(40)",
            "lab_area_sqft": "INTEGER",
            "lab_launch_date": "DATE",
            "assigned_trainer": "VARCHAR(160)",
            "current_students": "INTEGER DEFAULT 0",
            "girls_count": "INTEGER DEFAULT 0",
        },
    )
    add_missing(
        "students",
        {
            "father_name": "VARCHAR(160)",
            "mother_name": "VARCHAR(160)",
            "age": "INTEGER",
            "gender": "VARCHAR(40)",
            "caste": "VARCHAR(80)",
            "category": "VARCHAR(80)",
            "phone": "VARCHAR(40)",
            "address": "TEXT",
        },
    )
    add_missing(
        "batches",
        {
            "start_date": "DATE",
            "end_date": "DATE",
        },
    )


_ensure_columns()
Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    seed_initial_data(db)
    seed_lms_content(db)
    seed_curriculum_content(db)
    seed_handbook_volume_courses(db)

app = FastAPI(
    title="GTTC Student Dashboard & LMS",
    description="Student, trainer, school, and LMS extension for the GTTC portal.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

default_upload_dir = "/tmp/student-dashboard/uploads/lms" if os.getenv("VERCEL") else str(APP_DIR / "static" / "uploads" / "lms")
UPLOAD_DIR = Path(os.getenv("STUDENT_DASHBOARD_UPLOAD_DIR", default_upload_dir))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SESSION_COOKIE = "student_dashboard_session"
SESSION_VALUE = os.getenv("STUDENT_DASHBOARD_SESSION", "student-dashboard-local-session")
LOGIN_USERNAME = os.getenv("STUDENT_DASHBOARD_USERNAME", "admin@gttc.gov.in")
LOGIN_PASSWORD = os.getenv("STUDENT_DASHBOARD_PASSWORD", "Admin@123")


def _is_authenticated(request: Request):
    session = request.cookies.get(SESSION_COOKIE)
    return bool(session and (session == SESSION_VALUE or session.startswith("account:")))


def _current_account(request: Request):
    session = request.cookies.get(SESSION_COOKIE, "")
    if session == SESSION_VALUE:
        return {"name": "Admin User", "email": LOGIN_USERNAME, "role": "admin"}
    if not session.startswith("account:"):
        return None
    account_id = _parse_int(session.split(":")[1] if len(session.split(":")) > 1 else None)
    if not account_id:
        return None
    with SessionLocal() as db:
        account = db.query(models.Account).filter(models.Account.id == account_id).first()
        if not account:
            return None
        return {"name": account.name, "email": account.email, "role": account.role}


def _is_admin(request: Request):
    account = _current_account(request)
    return bool(account and account["role"] == "admin")


def _hash_password(password: str):
    return bcrypt.hashpw(password[:72].encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed_password: str):
    return bcrypt.checkpw(password[:72].encode(), hashed_password.encode())


def _set_session_cookie(response: RedirectResponse, value: str):
    response.set_cookie(
        SESSION_COOKIE,
        value,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 8,
    )


def _dashboard_redirect(message: str, kind: str = "success"):
    return RedirectResponse(f"/dashboard?{urlencode({'notice': message, 'notice_kind': kind})}", status_code=303)


def _parse_int(value, default=None):
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


PERFORMANCE_LEVELS = {"not_assessed", "needs_support", "developing", "proficient", "excellent"}
TEAMWORK_BADGES = {
    "ideator": "Ideator",
    "goal_getter": "Goal Getter",
    "co_creator": "Co-Creator",
    "questioner": "Questioner",
}


def _performance_level(value: str):
    return value if value in PERFORMANCE_LEVELS else "not_assessed"


def _worksheet_rows(upload: bytes):
    try:
        workbook = openpyxl.load_workbook(BytesIO(upload), data_only=True)
    except Exception as exc:
        raise HTTPException(400, f"Cannot parse Excel file: {exc}") from exc

    rows = list(workbook.active.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(400, "Empty Excel file")

    headers = [str(header).strip().lower() if header else "" for header in rows[0]]

    def col(row, name):
        try:
            value = row[headers.index(name)]
        except (ValueError, IndexError):
            return ""
        return str(value).strip() if value is not None else ""

    return rows[1:], col


def _matches_search(row: dict, search: str):
    if not search:
        return True
    needle = search.lower()
    return any(needle in str(value or "").lower() for value in row.values())


def _export_workbook(sheet_name: str, headers: list[str], rows: list[dict], filename: str):
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    worksheet.append(headers)

    for row in rows:
        worksheet.append([row.get(header, "") for header in headers])

    for column_cells in worksheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 14), 45)

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _safe_upload_name(filename: str):
    stem = Path(filename).stem or "content"
    suffix = Path(filename).suffix.lower()
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-")[:80] or "content"
    return f"{safe_stem}-{secrets.token_hex(6)}{suffix}"


def _validate_content_upload(content_type: str, upload: UploadFile | None, resource_url: str):
    allowed_extensions = {
        "pdf": {".pdf"},
        "ppt": {".ppt", ".pptx"},
        "video_file": {".mp4", ".mov", ".webm", ".mkv"},
    }
    if content_type == "video_link":
        _validate_video_link(resource_url)
        return

    if content_type not in allowed_extensions:
        raise ValueError("Unsupported content type.")
    if not upload or not upload.filename:
        raise ValueError("Please choose a file to upload.")

    extension = Path(upload.filename).suffix.lower()
    if extension not in allowed_extensions[content_type]:
        allowed = ", ".join(sorted(allowed_extensions[content_type]))
        raise ValueError(f"Invalid file type. Allowed: {allowed}.")


def _normalize_resource_url(resource_url: str):
    cleaned_url = resource_url.strip()
    if cleaned_url.startswith("/"):
        return cleaned_url
    if cleaned_url and not cleaned_url.startswith(("http://", "https://")):
        cleaned_url = f"https://{cleaned_url}"
    return cleaned_url


def _validate_video_link(resource_url: str):
    if not resource_url:
        raise ValueError("Video link is required.")
    parsed = urlparse(resource_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Video link must be a valid http:// or https:// URL.")


def _validate_optional_content_file(content_type: str, upload: UploadFile | None):
    allowed_extensions = {
        "pdf": {".pdf"},
        "ppt": {".ppt", ".pptx"},
        "video_file": {".mp4", ".mov", ".webm", ".mkv"},
    }
    if content_type in {"article", "video_link"}:
        return
    if content_type not in allowed_extensions:
        raise ValueError("Unsupported content type.")
    if not upload or not upload.filename:
        return
    extension = Path(upload.filename).suffix.lower()
    if extension not in allowed_extensions[content_type]:
        allowed = ", ".join(sorted(allowed_extensions[content_type]))
        raise ValueError(f"Invalid file type. Allowed: {allowed}.")


async def _save_content_upload(content_type: str, upload: UploadFile | None, resource_url: str):
    if content_type == "video_link":
        return resource_url.strip()
    if upload and upload.filename:
        safe_name = _safe_upload_name(upload.filename)
        target = UPLOAD_DIR / safe_name
        content = await upload.read()
        if not content:
            raise ValueError("Uploaded file is empty.")
        target.write_bytes(content)
        return f"/static/uploads/lms/{safe_name}"
    return ""


def _content_group(course_title: str, content_type: str):
    if course_title == "Volume I - Learning by Doing":
        return "volume-1"
    if course_title == "Volume II - Grades 6-8 ATL Activities":
        return "volume-2"
    if course_title == "Volume III - Grades 9-10 ATL Activities":
        return "volume-3"
    if content_type in {"pdf", "ppt", "video_link", "video_file"} and not course_title.startswith("Experiment "):
        return "uploaded"
    if course_title.startswith("Experiment "):
        return "experiments"
    if course_title == "ATL Curriculum and Innovation Calendar 2026-27":
        return "curriculum"
    return "other"


@app.get("/")
async def root(request: Request):
    if _is_authenticated(request):
        return RedirectResponse("/dashboard")
    return RedirectResponse("/login")


@app.get("/login")
async def login_page(request: Request):
    if _is_authenticated(request):
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "app_name": "GTTC Student Dashboard",
            "error": None,
            "username": LOGIN_USERNAME,
        },
    )


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    normalized_username = username.strip().lower()

    with SessionLocal() as db:
        account = db.query(models.Account).filter(func.lower(models.Account.email) == normalized_username).first()

    if account and _verify_password(password, account.hashed_password):
        response = RedirectResponse("/dashboard", status_code=303)
        _set_session_cookie(response, f"account:{account.id}:{secrets.token_urlsafe(16)}")
        return response

    valid_username = secrets.compare_digest(normalized_username, LOGIN_USERNAME.lower())
    valid_password = secrets.compare_digest(password, LOGIN_PASSWORD)

    if not (valid_username and valid_password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "app_name": "GTTC Student Dashboard",
                "error": "Invalid username or password.",
                "username": username,
            },
            status_code=401,
        )

    response = RedirectResponse("/dashboard", status_code=303)
    _set_session_cookie(response, SESSION_VALUE)
    return response


@app.get("/signup")
async def signup_page(request: Request):
    if _is_authenticated(request):
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse(
        request,
        "signup.html",
        {
            "app_name": "GTTC Student Dashboard",
            "error": None,
            "name": "",
            "email": "",
            "role": "student",
        },
    )


@app.post("/signup")
async def signup(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    role: str = Form("student"),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    normalized_email = email.strip().lower()
    cleaned_name = name.strip()
    allowed_roles = {"admin", "trainer", "school", "student"}
    selected_role = role if role in allowed_roles else "student"

    error = None
    if len(cleaned_name) < 2:
        error = "Please enter your full name."
    elif "@" not in normalized_email:
        error = "Please enter a valid email address."
    elif len(password) < 6:
        error = "Password must be at least 6 characters."
    elif password != confirm_password:
        error = "Passwords do not match."

    with SessionLocal() as db:
        exists = db.query(models.Account).filter(func.lower(models.Account.email) == normalized_email).first()
        if exists and not error:
            error = "An account with this email already exists."

        if error:
            return templates.TemplateResponse(
                request,
                "signup.html",
                {
                    "app_name": "GTTC Student Dashboard",
                    "error": error,
                    "name": cleaned_name,
                    "email": normalized_email,
                    "role": selected_role,
                },
                status_code=400,
            )

        account = models.Account(
            name=cleaned_name,
            email=normalized_email,
            role=selected_role,
            hashed_password=_hash_password(password),
        )
        db.add(account)
        db.commit()
        db.refresh(account)

    response = RedirectResponse("/dashboard", status_code=303)
    _set_session_cookie(response, f"account:{account.id}:{secrets.token_urlsafe(16)}")
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login")
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/bulk-template/{record_type}")
async def bulk_template(record_type: str, request: Request):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    templates = {
        "trainers": {
            "sheet": "Trainers",
            "headers": [
                "name", "email", "phone", "role", "gender", "caste",
                "division", "districts", "assigned_school", "specialization",
            ],
            "sample": [
                "Trainer Full Name", "trainer@example.com", "+91 9876543210", "atl_trainer",
                "female", "cat_2a", "Bengaluru", "Bengaluru South", "GHS Jayanagar", "ATL trainer",
            ],
        },
        "schools": {
            "sheet": "Schools",
            "headers": [
                "udise_code", "atl_lab_code", "name", "district", "division", "state",
                "pin_code", "school_type", "lab_type", "education_type", "max_grade",
                "principal_name", "principal_email", "principal_phone", "lab_area_sqft",
                "lab_launch_date", "assigned_trainer", "current_students", "girls_count",
            ],
            "sample": [
                "29XXXXXXXXX", "ATL-KA-999", "Government High School Example", "Mysore",
                "Mysuru", "Karnataka", "570001", "government", "atl", "secondary", "10",
                "Dr. Principal Name", "principal@example.edu", "+91 9876543210", "1200",
                "2023-01-15", "Trainer Full Name", "120", "55",
            ],
        },
        "students": {
            "sheet": "Students",
            "headers": [
                "name", "email", "grade", "school_udise_code", "father_name", "mother_name",
                "age", "gender", "caste", "category", "phone", "address",
            ],
            "sample": [
                "Student Full Name", "student@example.com", "8", "29XXXXXXXXX", "Father Name",
                "Mother Name", "13", "female", "SC", "Category A", "+91 9876543210", "Student address",
            ],
        },
    }
    config = templates.get(record_type)
    if not config:
        raise HTTPException(404, "Unknown template type")

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = config["sheet"]
    worksheet.append(config["headers"])
    worksheet.append(config["sample"])

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="student_dashboard_{record_type}_template.xlsx"'},
    )


@app.get("/export/{record_type}")
async def export_records(record_type: str, request: Request):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    search = request.query_params.get("q", "").strip()
    sort_key = request.query_params.get("sort", "").strip()
    direction = request.query_params.get("direction", "asc").strip().lower()
    reverse = direction == "desc"

    with SessionLocal() as db:
        if record_type == "trainers":
            headers = ["name", "email", "phone", "role", "division", "districts", "assigned_school", "specialization"]
            rows = [
                {
                    "name": trainer.name,
                    "email": trainer.email,
                    "phone": trainer.phone,
                    "role": trainer.role,
                    "division": trainer.division,
                    "districts": trainer.districts,
                    "assigned_school": trainer.assigned_school,
                    "specialization": trainer.specialization,
                }
                for trainer in db.query(models.Trainer).all()
            ]
            filename = "student_dashboard_trainers.xlsx"
            sheet_name = "Trainers"
        elif record_type == "schools":
            headers = [
                "udise_code", "atl_lab_code", "name", "division", "district", "principal_name",
                "assigned_trainer", "current_students", "girls_count",
            ]
            rows = [
                {
                    "udise_code": school.udise_code,
                    "atl_lab_code": school.atl_lab_code,
                    "name": school.name,
                    "division": school.division,
                    "district": school.district,
                    "principal_name": school.principal_name,
                    "assigned_trainer": school.assigned_trainer,
                    "current_students": school.current_students,
                    "girls_count": school.girls_count,
                }
                for school in db.query(models.School).all()
            ]
            filename = "student_dashboard_schools.xlsx"
            sheet_name = "Schools"
        elif record_type == "students":
            headers = [
                "name", "email", "grade", "school_name", "school_udise_code", "father_name",
                "mother_name", "age", "gender", "caste", "category", "phone", "address",
            ]
            rows = [
                {
                    "name": student.name,
                    "email": student.email,
                    "grade": student.grade,
                    "school_name": school_name,
                    "school_udise_code": school_udise_code,
                    "father_name": student.father_name,
                    "mother_name": student.mother_name,
                    "age": student.age,
                    "gender": student.gender,
                    "caste": student.caste,
                    "category": student.category,
                    "phone": student.phone,
                    "address": student.address,
                }
                for student, school_name, school_udise_code in (
                    db.query(models.Student, models.School.name.label("school_name"), models.School.udise_code.label("school_udise_code"))
                    .outerjoin(models.School, models.School.id == models.Student.school_id)
                    .all()
                )
            ]
            filename = "student_dashboard_students.xlsx"
            sheet_name = "Students"
        else:
            raise HTTPException(404, "Unknown export type")

    filtered_rows = [row for row in rows if _matches_search(row, search)]
    if sort_key in headers:
        filtered_rows.sort(key=lambda row: str(row.get(sort_key) or "").lower(), reverse=reverse)

    return _export_workbook(sheet_name, headers, filtered_rows, filename)


@app.post("/manual/trainer")
async def add_trainer(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    role: str = Form("atl_trainer"),
    division: str = Form(""),
    districts: str = Form(""),
    assigned_school: str = Form(""),
    specialization: str = Form("ATL trainer"),
):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    with SessionLocal() as db:
        if db.query(models.Trainer).filter(func.lower(models.Trainer.email) == email.strip().lower()).first():
            return _dashboard_redirect(f"Trainer email already exists: {email}", "error")
        db.add(
            models.Trainer(
                name=name.strip(),
                email=email.strip().lower(),
                phone=phone.strip() or None,
                role=role,
                division=division.strip() or None,
                districts=districts.strip() or None,
                assigned_school=assigned_school.strip() or None,
                specialization=specialization.strip() or None,
            )
        )
        db.commit()
    return _dashboard_redirect("Trainer added successfully.")


@app.post("/manual/school")
async def add_school(
    request: Request,
    udise_code: str = Form(...),
    atl_lab_code: str = Form(""),
    name: str = Form(...),
    district: str = Form(""),
    division: str = Form(""),
    pin_code: str = Form(""),
    principal_name: str = Form(""),
    assigned_trainer: str = Form(""),
    current_students: str = Form("0"),
    girls_count: str = Form("0"),
):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    with SessionLocal() as db:
        if db.query(models.School).filter(models.School.udise_code == udise_code.strip()).first():
            return _dashboard_redirect(f"School UDISE already exists: {udise_code}", "error")
        db.add(
            models.School(
                udise_code=udise_code.strip(),
                atl_lab_code=atl_lab_code.strip() or None,
                name=name.strip(),
                district=district.strip() or None,
                division=division.strip() or None,
                pin_code=pin_code.strip() or None,
                principal_name=principal_name.strip() or None,
                assigned_trainer=assigned_trainer.strip() or None,
                current_students=_parse_int(current_students, 0),
                girls_count=_parse_int(girls_count, 0),
            )
        )
        db.commit()
    return _dashboard_redirect("School added successfully.")


@app.post("/manual/student")
async def add_student(
    request: Request,
    name: str = Form(...),
    email: str = Form(""),
    grade: str = Form(""),
    school_udise_code: str = Form(""),
    father_name: str = Form(""),
    mother_name: str = Form(""),
    age: str = Form(""),
    gender: str = Form(""),
    caste: str = Form(""),
    category: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    with SessionLocal() as db:
        school = None
        if school_udise_code.strip():
            school = db.query(models.School).filter(models.School.udise_code == school_udise_code.strip()).first()
            if not school:
                return _dashboard_redirect(f"School UDISE not found: {school_udise_code}", "error")
        if email.strip() and db.query(models.Student).filter(func.lower(models.Student.email) == email.strip().lower()).first():
            return _dashboard_redirect(f"Student email already exists: {email}", "error")
        db.add(
            models.Student(
                name=name.strip(),
                email=email.strip().lower() or None,
                grade=grade.strip() or None,
                father_name=father_name.strip() or None,
                mother_name=mother_name.strip() or None,
                age=_parse_int(age),
                gender=gender.strip() or None,
                caste=caste.strip() or None,
                category=category.strip() or None,
                phone=phone.strip() or None,
                address=address.strip() or None,
                school_id=school.id if school else None,
            )
        )
        db.commit()
    return _dashboard_redirect("Student added successfully.")


@app.post("/bulk-upload/{record_type}")
async def bulk_upload(record_type: str, request: Request, file: UploadFile = File(...)):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    if record_type not in {"trainers", "schools", "students"}:
        raise HTTPException(404, "Unknown bulk upload type")

    rows, col = _worksheet_rows(await file.read())
    success, failed, errors = 0, 0, []

    with SessionLocal() as db:
        for index, row in enumerate(rows, start=2):
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue

            try:
                if record_type == "trainers":
                    name = col(row, "name") or col(row, "trainer_name")
                    email = (col(row, "email") or col(row, "trainer_email")).lower()
                    if not name or not email:
                        raise ValueError("missing name/email")
                    if db.query(models.Trainer).filter(func.lower(models.Trainer.email) == email).first():
                        raise ValueError(f"trainer email already exists: {email}")
                    db.add(
                        models.Trainer(
                            name=name,
                            email=email,
                            phone=col(row, "phone") or col(row, "trainer_phone") or None,
                            role=col(row, "role") or "atl_trainer",
                            gender=col(row, "gender") or col(row, "trainer_gender") or None,
                            caste=col(row, "caste") or col(row, "trainer_caste") or None,
                            division=col(row, "division") or None,
                            districts=col(row, "districts") or col(row, "district") or None,
                            assigned_school=col(row, "assigned_school") or None,
                            specialization=col(row, "specialization") or "ATL trainer",
                        )
                    )

                elif record_type == "schools":
                    udise = col(row, "udise_code")
                    name = col(row, "name")
                    if not udise or not name:
                        raise ValueError("missing udise_code/name")
                    if db.query(models.School).filter(models.School.udise_code == udise).first():
                        raise ValueError(f"school UDISE already exists: {udise}")
                    db.add(
                        models.School(
                            udise_code=udise,
                            atl_lab_code=col(row, "atl_lab_code") or None,
                            name=name,
                            district=col(row, "district") or None,
                            division=col(row, "division") or None,
                            state=col(row, "state") or "Karnataka",
                            pin_code=col(row, "pin_code") or None,
                            school_type=col(row, "school_type") or "government",
                            lab_type=col(row, "lab_type") or "atl",
                            education_type=col(row, "education_type") or "secondary",
                            max_grade=_parse_int(col(row, "max_grade"), 10),
                            principal_name=col(row, "principal_name") or None,
                            principal_email=col(row, "principal_email") or None,
                            principal_phone=col(row, "principal_phone") or None,
                            lab_area_sqft=_parse_int(col(row, "lab_area_sqft")),
                            lab_launch_date=_parse_date(col(row, "lab_launch_date")),
                            assigned_trainer=col(row, "assigned_trainer") or col(row, "trainer_name") or None,
                            current_students=_parse_int(col(row, "current_students"), 0),
                            girls_count=_parse_int(col(row, "girls_count"), 0),
                        )
                    )

                else:
                    name = col(row, "name") or col(row, "student_name")
                    email = (col(row, "email") or col(row, "student_email")).lower()
                    school_udise = col(row, "school_udise_code") or col(row, "udise_code")
                    if not name:
                        raise ValueError("missing student name")
                    school = None
                    if school_udise:
                        school = db.query(models.School).filter(models.School.udise_code == school_udise).first()
                        if not school:
                            raise ValueError(f"school UDISE not found: {school_udise}")
                    if email and db.query(models.Student).filter(func.lower(models.Student.email) == email).first():
                        raise ValueError(f"student email already exists: {email}")
                    db.add(
                        models.Student(
                            name=name,
                            email=email or None,
                            grade=col(row, "grade") or None,
                            father_name=col(row, "father_name") or col(row, "fathers_name") or None,
                            mother_name=col(row, "mother_name") or col(row, "mothers_name") or None,
                            age=_parse_int(col(row, "age")),
                            gender=col(row, "gender") or None,
                            caste=col(row, "caste") or None,
                            category=col(row, "category") or None,
                            phone=col(row, "phone") or col(row, "phone_number") or None,
                            address=col(row, "address") or None,
                            school_id=school.id if school else None,
                        )
                    )

                db.commit()
                success += 1
            except Exception as exc:
                db.rollback()
                failed += 1
                errors.append(f"Row {index}: {exc}")

    message = f"Bulk {record_type} upload complete: {success} success, {failed} failed."
    if errors:
        message += " " + " | ".join(errors[:3])
    return _dashboard_redirect(message, "error" if failed else "success")


@app.post("/content/upload")
async def upload_course_content(
    request: Request,
    course_id: int = Form(...),
    lesson_id: int = Form(...),
    title: str = Form(""),
    content_type: str = Form(...),
    resource_url: str = Form(""),
    content_body: str = Form(""),
    file: UploadFile | None = File(None),
):
    if not _is_authenticated(request):
        return RedirectResponse("/login")
    if not _is_admin(request):
        return _dashboard_redirect("Only admin can manage Content Library materials.", "error")

    cleaned_url = _normalize_resource_url(resource_url)

    try:
        _validate_content_upload(content_type, file, cleaned_url)
    except ValueError as exc:
        return _dashboard_redirect(str(exc), "error")

    saved_url = cleaned_url
    if content_type != "video_link" and file and file.filename:
        safe_name = _safe_upload_name(file.filename)
        target = UPLOAD_DIR / safe_name
        content = await file.read()
        if not content:
            return _dashboard_redirect("Uploaded file is empty.", "error")
        target.write_bytes(content)
        saved_url = f"/static/uploads/lms/{safe_name}"

    with SessionLocal() as db:
        course = db.query(models.Course).filter(models.Course.id == course_id).first()
        if not course:
            return _dashboard_redirect("Selected course was not found.", "error")
        lesson = (
            db.query(models.Lesson)
            .filter(models.Lesson.id == lesson_id, models.Lesson.course_id == course_id)
            .first()
        )
        if not lesson:
            return _dashboard_redirect("Selected lesson was not found for this course.", "error")
        db.add(
            models.LessonResource(
                lesson_id=lesson.id,
                title=title.strip() or f"{lesson.title} - {content_type.replace('_', ' ').title()}",
                content_type=content_type,
                content_body=content_body.strip() or f"Trainer uploaded {content_type.replace('_', ' ')} content.",
                resource_url=saved_url,
            )
        )
        db.commit()

    return _dashboard_redirect("Lesson resource uploaded successfully.")


@app.post("/content/update/{content_kind}/{content_id}")
async def update_course_content(
    request: Request,
    content_kind: str,
    content_id: int,
    title: str = Form(...),
    content_type: str = Form(...),
    resource_url: str = Form(""),
    content_body: str = Form(""),
    file: UploadFile | None = File(None),
):
    if not _is_authenticated(request):
        return RedirectResponse("/login")
    if not _is_admin(request):
        return _dashboard_redirect("Only admin can modify Content Library materials.", "error")

    cleaned_title = title.strip()
    cleaned_url = _normalize_resource_url(resource_url)
    if not cleaned_title:
        return _dashboard_redirect("Lesson title is required.", "error")
    if content_type == "video_link":
        try:
            _validate_video_link(cleaned_url)
        except ValueError as exc:
            return _dashboard_redirect(str(exc), "error")

    try:
        _validate_optional_content_file(content_type, file)
        saved_url = await _save_content_upload(content_type, file, cleaned_url)
    except ValueError as exc:
        return _dashboard_redirect(str(exc), "error")

    with SessionLocal() as db:
        if content_kind == "resource":
            content_item = db.query(models.LessonResource).filter(models.LessonResource.id == content_id).first()
            lesson_id = content_item.lesson_id if content_item else None
        else:
            content_item = db.query(models.Lesson).filter(models.Lesson.id == content_id).first()
            lesson_id = content_item.id if content_item else None
        if not content_item:
            return _dashboard_redirect("Selected content was not found.", "error")
        if content_type != content_item.content_type:
            if not saved_url:
                return _dashboard_redirect("Choose a file or paste a valid link to add this content type.", "error")
            db.add(
                models.LessonResource(
                    lesson_id=lesson_id,
                    title=cleaned_title,
                    content_type=content_type,
                    content_body=content_body.strip() or f"Trainer uploaded {content_type.replace('_', ' ')} content.",
                    resource_url=saved_url,
                )
            )
            db.commit()
            return _dashboard_redirect("New content added without replacing existing content.")
        if content_type != "video_link" and not saved_url and not content_item.resource_url:
            return _dashboard_redirect("Please choose a file or keep an existing resource.", "error")
        content_item.title = cleaned_title
        content_item.content_type = content_type
        content_item.content_body = content_body.strip() or ""
        if saved_url:
            content_item.resource_url = saved_url
        db.commit()

    return _dashboard_redirect("Content updated successfully.")


@app.post("/content/delete/{content_kind}/{content_id}")
async def delete_course_content(request: Request, content_kind: str, content_id: int):
    if not _is_authenticated(request):
        return RedirectResponse("/login")
    if not _is_admin(request):
        return _dashboard_redirect("Only admin can delete Content Library materials.", "error")

    with SessionLocal() as db:
        if content_kind == "resource":
            content_item = db.query(models.LessonResource).filter(models.LessonResource.id == content_id).first()
            if not content_item:
                return _dashboard_redirect("Selected content was not found.", "error")
            db.delete(content_item)
        else:
            lesson = db.query(models.Lesson).filter(models.Lesson.id == content_id).first()
            if not lesson:
                return _dashboard_redirect("Selected lesson was not found.", "error")
            lesson.content_type = "article"
            lesson.content_body = ""
            lesson.resource_url = None
        db.commit()

    return _dashboard_redirect("Content deleted successfully.")


@app.post("/enrollments/create")
async def create_enrollment(
    request: Request,
    student_id: int = Form(...),
    course_id: int = Form(...),
    assigned_by: str = Form("Trainer"),
):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    with SessionLocal() as db:
        student = db.query(models.Student).filter(models.Student.id == student_id).first()
        course = db.query(models.Course).filter(models.Course.id == course_id).first()
        if not student:
            return _dashboard_redirect("Selected student was not found.", "error")
        if not course:
            return _dashboard_redirect("Selected course was not found.", "error")
        existing = (
            db.query(models.Enrollment)
            .filter(models.Enrollment.student_id == student_id, models.Enrollment.course_id == course_id)
            .first()
        )
        if existing:
            return _dashboard_redirect("This student is already enrolled in the selected course.", "error")
        db.add(
            models.Enrollment(
                student_id=student_id,
                course_id=course_id,
                status="assigned",
                progress=0,
                assigned_by=assigned_by.strip() or "Trainer",
            )
        )
        db.commit()

    return _dashboard_redirect("Student enrolled into course successfully.")


@app.post("/enrollments/update")
async def update_enrollment(
    request: Request,
    enrollment_id: int = Form(...),
    status: str = Form(...),
    progress: int = Form(...),
):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    allowed_statuses = {"assigned", "in_progress", "completed", "dropped"}
    selected_status = status if status in allowed_statuses else "assigned"
    cleaned_progress = max(0, min(100, progress))

    with SessionLocal() as db:
        enrollment = db.query(models.Enrollment).filter(models.Enrollment.id == enrollment_id).first()
        if not enrollment:
            return _dashboard_redirect("Enrollment was not found.", "error")
        enrollment.status = selected_status
        enrollment.progress = cleaned_progress
        if selected_status == "completed" and cleaned_progress < 100:
            enrollment.progress = 100
        if selected_status == "completed":
            enrollment.completed_at = datetime.utcnow()
        db.commit()

    return _dashboard_redirect("Enrollment updated successfully.")


@app.post("/attendance/batches/create")
async def create_attendance_batch(
    request: Request,
    school_id: int = Form(...),
    name: str = Form(...),
    trainer_name: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    cleaned_name = name.strip()
    if not cleaned_name:
        return _dashboard_redirect("Batch name is required.", "error")
    parsed_start_date = _parse_date(start_date)
    parsed_end_date = _parse_date(end_date)
    if parsed_start_date and parsed_end_date and parsed_end_date < parsed_start_date:
        return _dashboard_redirect("Batch end date cannot be before start date.", "error")

    with SessionLocal() as db:
        school = db.query(models.School).filter(models.School.id == school_id).first()
        if not school:
            return _dashboard_redirect("Selected school was not found.", "error")
        exists = (
            db.query(models.Batch)
            .filter(models.Batch.school_id == school_id, func.lower(models.Batch.name) == cleaned_name.lower())
            .first()
        )
        if exists:
            return _dashboard_redirect("This batch already exists for the selected school.", "error")
        db.add(
            models.Batch(
                school_id=school_id,
                name=cleaned_name,
                trainer_name=trainer_name.strip() or None,
                start_date=parsed_start_date,
                end_date=parsed_end_date,
            )
        )
        db.commit()

    return _dashboard_redirect("Attendance batch created successfully.")


@app.post("/attendance/mark")
async def mark_attendance(
    request: Request,
    batch_id: int = Form(...),
    student_id: int = Form(...),
    attendance_date: str = Form(...),
    status: str = Form(...),
    marked_by: str = Form("Trainer"),
    remarks: str = Form(""),
):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    selected_date = _parse_date(attendance_date)
    if not selected_date:
        return _dashboard_redirect("Attendance date is required.", "error")
    selected_status = status if status in {"present", "absent", "late", "excused"} else "present"

    with SessionLocal() as db:
        batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
        student = db.query(models.Student).filter(models.Student.id == student_id).first()
        if not batch or not student:
            return _dashboard_redirect("Selected batch or student was not found.", "error")
        if student.school_id and student.school_id != batch.school_id:
            return _dashboard_redirect("Student does not belong to the selected batch school.", "error")
        record = (
            db.query(models.AttendanceRecord)
            .filter(
                models.AttendanceRecord.batch_id == batch_id,
                models.AttendanceRecord.student_id == student_id,
                models.AttendanceRecord.attendance_date == selected_date,
            )
            .first()
        )
        if not record:
            record = models.AttendanceRecord(batch_id=batch_id, student_id=student_id, attendance_date=selected_date)
            db.add(record)
        record.status = selected_status
        record.marked_by = marked_by.strip() or "Trainer"
        record.remarks = remarks.strip() or None
        db.commit()

    return _dashboard_redirect("Attendance saved successfully.")


@app.post("/attendance/mark-bulk")
async def mark_bulk_attendance(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    form = await request.form()
    batch_id = _parse_int(form.get("batch_id"))
    selected_date = _parse_date(form.get("attendance_date"))
    marked_by = str(form.get("marked_by") or "Trainer").strip() or "Trainer"
    remarks = str(form.get("remarks") or "").strip() or None
    if not batch_id or not selected_date:
        return _dashboard_redirect("Batch and attendance date are required.", "error")

    saved_count = 0
    with SessionLocal() as db:
        batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
        if not batch:
            return _dashboard_redirect("Selected batch was not found.", "error")
        students = db.query(models.Student).filter(models.Student.school_id == batch.school_id).order_by(models.Student.name).all()
        for student in students:
            selected_status = form.get(f"status_{student.id}")
            if selected_status not in {"present", "absent"}:
                continue
            record = (
                db.query(models.AttendanceRecord)
                .filter(
                    models.AttendanceRecord.batch_id == batch.id,
                    models.AttendanceRecord.student_id == student.id,
                    models.AttendanceRecord.attendance_date == selected_date,
                )
                .first()
            )
            if not record:
                record = models.AttendanceRecord(batch_id=batch.id, student_id=student.id, attendance_date=selected_date)
                db.add(record)
            record.status = selected_status
            record.marked_by = marked_by
            record.remarks = remarks
            saved_count += 1
        db.commit()

    if not saved_count:
        return _dashboard_redirect("No students were available to mark for this batch school.", "error")
    return _dashboard_redirect(f"Attendance saved for {saved_count} student(s).")


@app.post("/performance/batch-assessment")
async def save_batch_performance(
    request: Request,
    batch_id: int = Form(...),
    concept_understanding: str = Form("not_assessed"),
    project_understanding: str = Form("not_assessed"),
    design_thinking: str = Form("not_assessed"),
    assessed_by: str = Form("Trainer"),
    remarks: str = Form(""),
):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    with SessionLocal() as db:
        batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
        if not batch:
            return _dashboard_redirect("Selected batch was not found.", "error")
        assessment = (
            db.query(models.BatchPerformanceAssessment)
            .filter(models.BatchPerformanceAssessment.batch_id == batch.id)
            .first()
        )
        if not assessment:
            assessment = models.BatchPerformanceAssessment(batch_id=batch.id)
            db.add(assessment)
        assessment.concept_understanding = _performance_level(concept_understanding)
        assessment.project_understanding = _performance_level(project_understanding)
        assessment.design_thinking = _performance_level(design_thinking)
        assessment.assessed_by = assessed_by.strip() or "Trainer"
        assessment.remarks = remarks.strip() or None
        assessment.assessed_at = datetime.utcnow()
        db.commit()

    return _dashboard_redirect("Batch performance assessment saved successfully.")


@app.post("/performance/teamwork-badges")
async def save_teamwork_badges(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    form = await request.form()
    batch_id = _parse_int(form.get("batch_id"))
    assigned_by = str(form.get("assigned_by") or "Trainer").strip() or "Trainer"
    remarks = str(form.get("remarks") or "").strip() or None
    if not batch_id:
        return _dashboard_redirect("Select a batch before assigning teamwork badges.", "error")

    with SessionLocal() as db:
        batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
        if not batch:
            return _dashboard_redirect("Selected batch was not found.", "error")
        saved_count = 0
        for badge_key in TEAMWORK_BADGES:
            student_id = _parse_int(form.get(f"badge_{badge_key}"))
            existing = (
                db.query(models.StudentTeamworkBadge)
                .filter(models.StudentTeamworkBadge.batch_id == batch.id, models.StudentTeamworkBadge.badge == badge_key)
                .all()
            )
            for badge_record in existing:
                db.delete(badge_record)
            if not student_id:
                continue
            student = db.query(models.Student).filter(models.Student.id == student_id).first()
            if not student or student.school_id != batch.school_id:
                return _dashboard_redirect("Selected badge student does not belong to this batch school.", "error")
            db.add(
                models.StudentTeamworkBadge(
                    batch_id=batch.id,
                    student_id=student.id,
                    badge=badge_key,
                    assigned_by=assigned_by,
                    remarks=remarks,
                    assigned_at=datetime.utcnow(),
                )
            )
            saved_count += 1
        db.commit()

    return _dashboard_redirect(f"Teamwork badge assignment saved for {saved_count} badge(s).")


@app.get("/attendance/export")
async def export_attendance(
    request: Request,
    scope: str = "day",
    group: str = "individual",
    school_id: int | None = None,
    batch_id: int | None = None,
    attendance_date: str = "",
):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    selected_date = _parse_date(attendance_date) if scope == "day" else None
    if scope == "day" and not selected_date:
        return _dashboard_redirect("Select a date before downloading day-wise attendance.", "error")

    with SessionLocal() as db:
        query = (
            db.query(models.AttendanceRecord, models.Batch, models.Student, models.School)
            .join(models.Batch, models.Batch.id == models.AttendanceRecord.batch_id)
            .join(models.Student, models.Student.id == models.AttendanceRecord.student_id)
            .join(models.School, models.School.id == models.Batch.school_id)
        )
        if school_id:
            query = query.filter(models.Batch.school_id == school_id)
        if batch_id:
            query = query.filter(models.AttendanceRecord.batch_id == batch_id)
        if selected_date:
            query = query.filter(models.AttendanceRecord.attendance_date == selected_date)
        records = query.order_by(models.School.name, models.Batch.name, models.Student.name, models.AttendanceRecord.attendance_date).all()

    if group == "batch":
        summary = {}
        for record, batch, _student, school in records:
            key = (school.name, batch.name)
            bucket = summary.setdefault(
                key,
                {"school": school.name, "batch": batch.name, "trainer": batch.trainer_name or "", "days": set(), "total": 0, "present": 0, "absent": 0},
            )
            bucket["days"].add(record.attendance_date)
            bucket["total"] += 1
            if record.status == "present":
                bucket["present"] += 1
            elif record.status == "absent":
                bucket["absent"] += 1
        rows = [
            {
                "school": item["school"],
                "batch": item["batch"],
                "trainer": item["trainer"],
                "days_marked": len(item["days"]),
                "total_records": item["total"],
                "present": item["present"],
                "absent": item["absent"],
                "present_percent": round((item["present"] / item["total"]) * 100) if item["total"] else 0,
            }
            for item in summary.values()
        ]
        return _export_workbook(
            "Batch Attendance",
            ["school", "batch", "trainer", "days_marked", "total_records", "present", "absent", "present_percent"],
            rows,
            f"attendance-{scope}-batch.xlsx",
        )

    summary = {}
    for record, batch, student, school in records:
        if scope == "day":
            summary[(batch.id, student.id, record.attendance_date)] = {
                "date": record.attendance_date,
                "school": school.name,
                "batch": batch.name,
                "student": student.name,
                "status": record.status,
                "marked_by": record.marked_by or "",
                "remarks": record.remarks or "",
            }
        else:
            key = (batch.id, student.id)
            bucket = summary.setdefault(
                key,
                {"school": school.name, "batch": batch.name, "student": student.name, "total": 0, "present": 0, "absent": 0},
            )
            bucket["total"] += 1
            if record.status == "present":
                bucket["present"] += 1
            elif record.status == "absent":
                bucket["absent"] += 1

    if scope == "day":
        rows = list(summary.values())
        headers = ["date", "school", "batch", "student", "status", "marked_by", "remarks"]
    else:
        rows = [
            {
                **item,
                "present_percent": round((item["present"] / item["total"]) * 100) if item["total"] else 0,
            }
            for item in summary.values()
        ]
        headers = ["school", "batch", "student", "total", "present", "absent", "present_percent"]
    return _export_workbook("Individual Attendance", headers, rows, f"attendance-{scope}-individual.xlsx")


@app.get("/dashboard")
async def dashboard(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    current_account = _current_account(request) or {"name": "User", "email": "", "role": "student"}
    is_admin = current_account["role"] == "admin"

    with SessionLocal() as db:
        trainers = db.query(models.Trainer).order_by(models.Trainer.role.desc(), models.Trainer.name).all()
        schools = db.query(models.School).order_by(models.School.division, models.School.district, models.School.name).all()
        students = (
            db.query(models.Student, models.School.name.label("school_name"), models.School.udise_code.label("school_udise_code"))
            .outerjoin(models.School, models.School.id == models.Student.school_id)
            .order_by(models.Student.name)
            .all()
        )
        student_rows = [
            {
                "id": student.id,
                "name": student.name,
                "email": student.email,
                "grade": student.grade,
                "father_name": student.father_name,
                "mother_name": student.mother_name,
                "age": student.age,
                "gender": student.gender,
                "caste": student.caste,
                "category": student.category,
                "phone": student.phone,
                "address": student.address,
                "school_id": student.school_id,
                "school_name": school_name,
                "school_udise_code": school_udise_code,
            }
            for student, school_name, school_udise_code in students
        ]
        students_count = len(student_rows)
        courses_count = db.query(func.count(models.Course.id)).scalar() or 0
        lessons_count = db.query(func.count(models.Lesson.id)).scalar() or 0
        courses = db.query(models.Course).order_by(models.Course.id).all()
        course_rows = [
            {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "level": course.level,
                "lesson_count": db.query(func.count(models.Lesson.id)).filter(models.Lesson.course_id == course.id).scalar() or 0,
            }
            for course in courses
        ]
        lesson_options_by_course = {
            str(course.id): [
                {"id": lesson.id, "title": lesson.title}
                for lesson in db.query(models.Lesson)
                .filter(models.Lesson.course_id == course.id)
                .order_by(models.Lesson.sort_order, models.Lesson.id)
                .all()
            ]
            for course in courses
        }
        volume_columns = []
        for volume in VOLUME_COURSES:
            course = next((row for row in course_rows if row["title"] == volume["title"]), None)
            if not course:
                continue
            lessons = (
                db.query(models.Lesson)
                .filter(models.Lesson.course_id == course["id"])
                .order_by(models.Lesson.sort_order, models.Lesson.id)
                .all()
            )
            volume_columns.append(
                {
                    "title": volume["title"],
                    "level": volume["level"],
                    "description": volume["description"],
                    "resource_url": volume["resource_url"],
                    "lesson_count": len(lessons),
                    "lessons": [
                        {
                            "title": lesson.title,
                            "content_type": lesson.content_type,
                            "content_body": lesson.content_body,
                            "resource_url": lesson.resource_url,
                        }
                        for lesson in lessons
                    ],
                }
            )
        content_rows = []
        for course in courses:
            lessons = (
                db.query(models.Lesson)
                .filter(models.Lesson.course_id == course.id)
                .order_by(models.Lesson.sort_order, models.Lesson.id)
                .all()
            )
            for lesson in lessons:
                resources = (
                    db.query(models.LessonResource)
                    .filter(models.LessonResource.lesson_id == lesson.id)
                    .order_by(models.LessonResource.created_at, models.LessonResource.id)
                    .all()
                )
                lesson_resources = [
                    {
                        "id": resource.id,
                        "kind": "resource",
                        "title": resource.title,
                        "content_type": resource.content_type,
                        "content_body": resource.content_body or "",
                        "resource_url": resource.resource_url or "",
                    }
                    for resource in resources
                ]
                if lesson.resource_url or lesson.content_type != "article":
                    lesson_resources.insert(
                        0,
                        {
                            "id": lesson.id,
                            "kind": "lesson",
                            "title": lesson.title,
                            "content_type": lesson.content_type,
                            "content_body": lesson.content_body or "",
                            "resource_url": lesson.resource_url or "",
                        },
                    )
                content_rows.append(
                    {
                        "id": lesson.id,
                        "kind": "lesson",
                        "course_title": course.title,
                        "lesson_title": lesson.title,
                        "content_title": lesson.title,
                        "content_type": "multiple" if lesson_resources else lesson.content_type,
                        "content_body": f"{len(lesson_resources)} uploaded content item(s)." if lesson_resources else (lesson.content_body or ""),
                        "resource_url": "",
                        "resources": lesson_resources,
                        "group": _content_group(course.title, lesson.content_type),
                    }
                )
        content_counts = {
            "all": len(content_rows),
            "volume-1": sum(1 for row in content_rows if row["group"] == "volume-1"),
            "volume-2": sum(1 for row in content_rows if row["group"] == "volume-2"),
            "volume-3": sum(1 for row in content_rows if row["group"] == "volume-3"),
            "uploaded": sum(1 for row in content_rows if row["group"] == "uploaded"),
            "experiments": sum(1 for row in content_rows if row["group"] == "experiments"),
            "curriculum": sum(1 for row in content_rows if row["group"] == "curriculum"),
        }
        enrollments = (
            db.query(models.Enrollment, models.Student, models.Course, models.School)
            .join(models.Student, models.Student.id == models.Enrollment.student_id)
            .join(models.Course, models.Course.id == models.Enrollment.course_id)
            .outerjoin(models.School, models.School.id == models.Student.school_id)
            .order_by(models.Enrollment.assigned_at.desc())
            .all()
        )
        enrollment_rows = [
            {
                "id": enrollment.id,
                "student_name": student.name,
                "student_email": student.email,
                "school_name": school.name if school else None,
                "course_title": course.title,
                "status": enrollment.status,
                "progress": enrollment.progress or 0,
                "assigned_by": enrollment.assigned_by,
            }
            for enrollment, student, course, school in enrollments
        ]
        batches = (
            db.query(models.Batch, models.School)
            .join(models.School, models.School.id == models.Batch.school_id)
            .order_by(models.School.name, models.Batch.name)
            .all()
        )
        batch_rows = [
            {
                "id": batch.id,
                "school_id": batch.school_id,
                "school_name": school.name,
                "name": batch.name,
                "trainer_name": batch.trainer_name,
                "schedule": batch.schedule,
                "start_date": batch.start_date,
                "end_date": batch.end_date,
            }
            for batch, school in batches
        ]
        attendance_records = (
            db.query(models.AttendanceRecord, models.Batch, models.Student, models.School)
            .join(models.Batch, models.Batch.id == models.AttendanceRecord.batch_id)
            .join(models.Student, models.Student.id == models.AttendanceRecord.student_id)
            .join(models.School, models.School.id == models.Batch.school_id)
            .order_by(models.AttendanceRecord.attendance_date.desc(), models.School.name, models.Batch.name, models.Student.name)
            .all()
        )
        report_map = {}
        student_report_map = {}
        batch_performance_map = {}
        attendance_status_map = {}
        attendance_rows = []
        for record, batch, student, school in attendance_records:
            attendance_status_map[f"{batch.id}:{record.attendance_date.isoformat()}:{student.id}"] = record.status
            school_bucket = report_map.setdefault(
                school.id,
                {"school_id": school.id, "school_name": school.name, "batches": {}, "total": 0, "present": 0, "absent": 0, "late": 0, "excused": 0},
            )
            batch_bucket = school_bucket["batches"].setdefault(
                batch.id,
                {"batch_id": batch.id, "batch_name": batch.name, "trainer_name": batch.trainer_name, "total": 0, "present": 0, "absent": 0, "late": 0, "excused": 0, "dates": set()},
            )
            student_bucket = student_report_map.setdefault(
                (batch.id, student.id),
                {
                    "school_id": school.id,
                    "batch_id": batch.id,
                    "student_name": student.name,
                    "school_name": school.name,
                    "batch_name": batch.name,
                    "total": 0,
                    "present": 0,
                    "absent": 0,
                    "late": 0,
                    "excused": 0,
                },
            )
            performance_bucket = batch_performance_map.setdefault(
                batch.id,
                {
                    "school_id": school.id,
                    "batch_id": batch.id,
                    "school_name": school.name,
                    "batch_name": batch.name,
                    "trainer_name": batch.trainer_name,
                    "total": 0,
                    "present": 0,
                    "absent": 0,
                    "late": 0,
                    "excused": 0,
                    "dates": set(),
                },
            )
            school_bucket["total"] += 1
            batch_bucket["total"] += 1
            batch_bucket["dates"].add(record.attendance_date)
            student_bucket["total"] += 1
            performance_bucket["total"] += 1
            performance_bucket["dates"].add(record.attendance_date)
            if record.status in {"present", "absent", "late", "excused"}:
                school_bucket[record.status] += 1
                batch_bucket[record.status] += 1
                student_bucket[record.status] += 1
                performance_bucket[record.status] += 1
            attendance_rows.append(
                {
                    "date": record.attendance_date,
                    "school_id": school.id,
                    "batch_id": batch.id,
                    "school_name": school.name,
                    "batch_name": batch.name,
                    "student_name": student.name,
                    "status": record.status,
                    "marked_by": record.marked_by,
                    "remarks": record.remarks,
                }
            )
        attendance_report = [
            {
                **school_data,
                "batches": [
                    {
                        **batch_data,
                        "days_marked": len(batch_data["dates"]),
                        "present_percent": round((batch_data["present"] / batch_data["total"]) * 100) if batch_data["total"] else 0,
                    }
                    for batch_data in school_data["batches"].values()
                ],
            }
            for school_data in report_map.values()
        ]
        individual_attendance_report = [
            {
                **student_data,
                "present_percent": round((student_data["present"] / student_data["total"]) * 100) if student_data["total"] else 0,
            }
            for student_data in student_report_map.values()
        ]
        batch_performance_report = [
            {
                **batch_data,
                "days_marked": len(batch_data["dates"]),
                "present_percent": round((batch_data["present"] / batch_data["total"]) * 100) if batch_data["total"] else 0,
            }
            for batch_data in batch_performance_map.values()
        ]
        batch_assessments = db.query(models.BatchPerformanceAssessment).all()
        batch_assessment_map = {assessment.batch_id: assessment for assessment in batch_assessments}
        teamwork_badges = (
            db.query(models.StudentTeamworkBadge, models.Batch, models.Student, models.School)
            .join(models.Batch, models.Batch.id == models.StudentTeamworkBadge.batch_id)
            .join(models.Student, models.Student.id == models.StudentTeamworkBadge.student_id)
            .join(models.School, models.School.id == models.Batch.school_id)
            .order_by(models.School.name, models.Batch.name, models.StudentTeamworkBadge.badge)
            .all()
        )
        teamwork_badge_map = {
            f"{badge.batch_id}:{badge.badge}": badge.student_id
            for badge, _batch, _student, _school in teamwork_badges
        }
        batch_assessment_form_map = {
            str(assessment.batch_id): {
                "concept_understanding": assessment.concept_understanding,
                "project_understanding": assessment.project_understanding,
                "design_thinking": assessment.design_thinking,
                "assessed_by": assessment.assessed_by or "",
                "remarks": assessment.remarks or "",
            }
            for assessment in batch_assessments
        }
        teamwork_badge_rows = [
            {
                "school_id": school.id,
                "school_name": school.name,
                "batch_id": batch.id,
                "batch_name": batch.name,
                "student_name": student.name,
                "badge": badge.badge,
                "badge_label": TEAMWORK_BADGES.get(badge.badge, badge.badge),
                "assigned_by": badge.assigned_by,
                "remarks": badge.remarks,
            }
            for badge, batch, student, school in teamwork_badges
        ]
        performance_assessment_rows = [
            {
                "school_id": batch["school_id"],
                "school_name": batch["school_name"],
                "batch_id": batch["id"],
                "batch_name": batch["name"],
                "trainer_name": batch["trainer_name"],
                "concept_understanding": (batch_assessment_map.get(batch["id"]).concept_understanding if batch_assessment_map.get(batch["id"]) else "not_assessed"),
                "project_understanding": (batch_assessment_map.get(batch["id"]).project_understanding if batch_assessment_map.get(batch["id"]) else "not_assessed"),
                "design_thinking": (batch_assessment_map.get(batch["id"]).design_thinking if batch_assessment_map.get(batch["id"]) else "not_assessed"),
                "assessed_by": (batch_assessment_map.get(batch["id"]).assessed_by if batch_assessment_map.get(batch["id"]) else None),
                "remarks": (batch_assessment_map.get(batch["id"]).remarks if batch_assessment_map.get(batch["id"]) else None),
            }
            for batch in batch_rows
        ]
        total_student_count = sum(school.current_students or 0 for school in schools)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "app_name": "GTTC Student Dashboard",
            "module_name": "Student + LMS Extension",
            "current_account": current_account,
            "is_admin": is_admin,
            "trainers": trainers,
            "schools": schools,
            "trainers_count": len(trainers),
            "schools_count": len(schools),
            "students_count": students_count,
            "students": student_rows,
            "courses_count": courses_count,
            "lessons_count": lessons_count,
            "courses": course_rows,
            "lesson_options_by_course": lesson_options_by_course,
            "volume_columns": volume_columns,
            "content_rows": content_rows,
            "content_counts": content_counts,
            "enrollments": enrollment_rows,
            "enrollments_count": len(enrollment_rows),
            "batches": batch_rows,
            "attendance_rows": attendance_rows[:30],
            "attendance_report": attendance_report,
            "individual_attendance_report": individual_attendance_report,
            "batch_performance_report": batch_performance_report,
            "performance_levels": [
                ("not_assessed", "Not Assessed"),
                ("needs_support", "Needs Support"),
                ("developing", "Developing"),
                ("proficient", "Proficient"),
                ("excellent", "Excellent"),
            ],
            "teamwork_badges": TEAMWORK_BADGES,
            "teamwork_badge_map": teamwork_badge_map,
            "batch_assessment_form_map": batch_assessment_form_map,
            "teamwork_badge_rows": teamwork_badge_rows,
            "performance_assessment_rows": performance_assessment_rows,
            "attendance_status_map": attendance_status_map,
            "today": date.today().isoformat(),
            "total_student_count": total_student_count,
            "notice": request.query_params.get("notice"),
            "notice_kind": request.query_params.get("notice_kind", "success"),
        },
    )


@app.get("/health")
async def health():
    return {"ok": True, "service": "student-dashboard"}
