from datetime import date
import random

from app.models.users import User, RoleEnum, GenderEnum, CasteEnum
from app.models.hierarchy import Division, School, SchoolTrainer, SchoolPrincipal, LabTypeEnum, SchoolTypeEnum, EducationTypeEnum
from app.models.reports import MonthlyReport, ReportStatusEnum
from app.core.security import hash_password


DIVISION_DISTRICTS = {
    "Bengaluru": ["Bengaluru South", "Bengaluru North", "Tumkur"],
    "Belagavi":  ["Belagavi", "Dharwad", "Vijayapura"],
    "Mysuru":    ["Mysore", "Hassan", "Udupi"],
    "Kalburgi":  ["Kalburgi", "Raichur", "Bidar"],
}

MASTER_TRAINERS = [
    {"name": "Amit Kumar",   "email": "amit.kumar@gttc.gov.in",  "division": "Bengaluru", "gender": "male", "caste": "cat_1",
     "districts": ["Bengaluru South", "Bengaluru North", "Tumkur"]},
    {"name": "Rajesh Patil", "email": "rajesh.patil@gttc.gov.in","division": "Belagavi",  "gender": "male", "caste": "cat_3a",
     "districts": ["Belagavi", "Dharwad", "Vijayapura"]},
    {"name": "Mohan Gowda",  "email": "mohan.gowda@gttc.gov.in", "division": "Mysuru",    "gender": "male", "caste": "sc",
     "districts": ["Mysore", "Hassan", "Udupi"]},
    {"name": "Sunil Reddy",  "email": "sunil.reddy@gttc.gov.in", "division": "Kalburgi",  "gender": "male", "caste": "st",
     "districts": ["Kalburgi", "Raichur", "Bidar"]},
]

SCHOOL_DATA = [
    ("29010001001", "ATL-KA-001", "GHS Jayanagar",        "Bengaluru South", "560041"),
    ("29010001002", "ATL-KA-002", "GHS Yelahanka",        "Bengaluru North", "560064"),
    ("29020002001", "ATL-KA-003", "GHS Belagavi City",    "Belagavi",        "590001"),
    ("29020002002", "ATL-KA-004", "GHS Dharwad",          "Dharwad",         "580001"),
    ("29030003001", "ATL-KA-005", "GGHS Saraswathipuram", "Mysore",          "570009"),
    ("29030003002", "ATL-KA-006", "GHS Hassan",           "Hassan",          "573201"),
    ("29040004001", "ATL-KA-007", "GHS Kalburgi North",   "Kalburgi",        "585101"),
    ("29040004002", "ATL-KA-008", "GHS Raichur",          "Raichur",         "584101"),
]

TRAINER_DATA = [
    ("Suresh Muthu",  "suresh.muthu",  "male",   "sc"),
    ("Kavitha Reddy", "kavitha.reddy", "female", "cat_2a"),
    ("Rajesh Naik",   "rajesh.naik",   "male",   "cat_3a"),
    ("Priya Sharma",  "priya.sharma",  "female", "cat_1"),
    ("Anil Gowda",    "anil.gowda",    "male",   "cat_2b"),
    ("Meena Nair",    "meena.nair",    "female", "other"),
    ("Vinod Kumar",   "vinod.kumar",   "male",   "cat_1"),
    ("Suma Joshi",    "suma.joshi",    "female", "sc"),
]

PRINCIPAL_DATA = [
    ("Dr. Ramesh M",  "p.ramesh.m"),
    ("Mrs. Sudha K",  "p.sudha.k"),
    ("Mr. Nagesh R",  "p.nagesh.r"),
    ("Dr. Anand S",   "p.anand.s"),
    ("Mrs. Latha C",  "p.latha.c"),
    ("Dr. Kishore P", "p.kishore.p"),
    ("Mr. Sanjay T",  "p.sanjay.t"),
    ("Mrs. Geetha N", "p.geetha.n"),
]

# 5 months of AY 2025-26, each report is a running YTD total
REPORT_MONTHS = [
    (2025, 11, "2025-26"),
    (2025, 12, "2025-26"),
    (2026,  1, "2025-26"),
    (2026,  2, "2025-26"),
    (2026,  3, "2025-26"),
]


def _running_totals(rng):
    """Generate 5 months of running totals for one school."""
    students      = rng.randint(60, 130)
    girls         = rng.randint(20, students // 2)
    community     = rng.randint(10, 35)
    workshops     = 0
    mentoring     = 0
    innovation    = 0
    patents       = 0
    copyrights    = 0
    atl_part      = 0
    atl_won       = 0
    other_part    = 0
    other_won     = 0

    months = []
    for i, (year, month, acad) in enumerate(REPORT_MONTHS):
        # Students may grow slightly once or twice during the year
        if i > 0 and rng.random() < 0.25:
            students  += rng.randint(5, 20)
            girls     += rng.randint(2, 8)
            girls      = min(girls, students // 2)
        if i > 0 and rng.random() < 0.15:
            community += rng.randint(5, 15)

        # Activities accumulate each month
        workshops  += rng.randint(1, 4)
        mentoring  += rng.randint(1, 5)
        innovation += rng.randint(0, 3)
        patents    += rng.randint(0, 1)
        copyrights += rng.randint(0, 1)
        atl_part   += rng.randint(0, 2)
        atl_won    += rng.randint(0, 1)
        other_part += rng.randint(0, 2)
        other_won  += rng.randint(0, 1)

        months.append({
            "year": year, "month": month, "acad": acad,
            "students_school":    students,
            "students_girls":     girls,
            "students_community": community,
            "workshops_school":   workshops,
            "workshops_community": 0,
            "mentoring_school":   mentoring,
            "mentoring_community": 0,
            "innovation_school":  innovation,
            "innovation_community": 0,
            "patents_school":     patents,
            "patents_community":  0,
            "copyrights_school":  copyrights,
            "copyrights_community": 0,
            "atl_competitions_participated":   atl_part,
            "atl_competitions_won":            atl_won,
            "other_competitions_participated": other_part,
            "other_competitions_won":          other_won,
            "highlight": random.choice([
                "Robotics workshop conducted",
                "Students won district ATL competition",
                "3D printing project completed",
                None,
            ]),
        })
    return months


def seed_initial_data(db):
    if db.query(User).filter(User.role == RoleEnum.state_admin).first():
        fix_existing_reports(db)
        return
    admin = User(
        name="SPD-Samagra Shikshana Karnataka",
        email="admin@gttc.gov.in",
        hashed_password=hash_password("sdp@samagra-2026"),
        role=RoleEnum.state_admin,
        is_active=True,
        must_change_password=False,
    )
    db.add(admin)
    db.commit()
    _seed_demo(db, admin.id)


def fix_existing_reports(db):
    """
    Convert any existing per-month reports into running YTD totals.
    Groups reports by school, sorts by date, accumulates values forward.
    Only runs once — skips schools that already have monotonically increasing workshops.
    """
    from app.models.reports import MonthlyReport
    from sqlalchemy import func

    schools_with_reports = db.query(MonthlyReport.school_id).distinct().all()
    changed = False

    for (school_id,) in schools_with_reports:
        reports = (
            db.query(MonthlyReport)
            .filter(MonthlyReport.school_id == school_id)
            .order_by(MonthlyReport.report_year, MonthlyReport.report_month)
            .all()
        )
        if len(reports) < 2:
            continue

        # Check if already running totals (workshops non-decreasing)
        already_running = all(
            reports[i].workshops_school >= reports[i-1].workshops_school
            for i in range(1, len(reports))
        )
        if already_running:
            continue

        # Accumulate forward
        ws_s = ws_c = ment_s = ment_c = 0
        inn_s = inn_c = pat_s = pat_c = copy_s = copy_c = 0
        atl_p = atl_w = oth_p = oth_w = 0

        for r in reports:
            ws_s   += r.workshops_school   or 0
            ws_c   += r.workshops_community or 0
            ment_s += r.mentoring_school   or 0
            ment_c += r.mentoring_community or 0
            inn_s  += r.innovation_school  or 0
            inn_c  += r.innovation_community or 0
            pat_s  += r.patents_school     or 0
            pat_c  += r.patents_community  or 0
            copy_s += r.copyrights_school  or 0
            copy_c += r.copyrights_community or 0
            atl_p  += r.atl_competitions_participated or 0
            atl_w  += r.atl_competitions_won          or 0
            oth_p  += r.other_competitions_participated or 0
            oth_w  += r.other_competitions_won          or 0

            r.workshops_school    = ws_s
            r.workshops_community = ws_c
            r.mentoring_school    = ment_s
            r.mentoring_community = ment_c
            r.innovation_school   = inn_s
            r.innovation_community= inn_c
            r.patents_school      = pat_s
            r.patents_community   = pat_c
            r.copyrights_school   = copy_s
            r.copyrights_community= copy_c
            r.atl_competitions_participated   = atl_p
            r.atl_competitions_won            = atl_w
            r.other_competitions_participated = oth_p
            r.other_competitions_won          = oth_w
            changed = True

    if changed:
        db.commit()


def _seed_demo(db, admin_id):
    if db.query(Division).first():
        return

    divs = {}
    for div_name in DIVISION_DISTRICTS:
        d = Division(name=div_name, code=div_name[:3].upper(), state="Karnataka")
        db.add(d)
        db.flush()
        divs[div_name] = d
    db.commit()

    for div_name, div in divs.items():
        dm = User(
            name=f"SPM GTTC {div_name}",
            email=f"spm.{div_name.lower()[:3]}@gttc.gov.in",
            hashed_password=hash_password("Pass@1234"),
            role=RoleEnum.division_master,
            division_id=div.id,
            is_active=True,
            must_change_password=True,
        )
        db.add(dm)

    for mt_data in MASTER_TRAINERS:
        div = divs[mt_data["division"]]
        mt = User(
            name=mt_data["name"],
            email=mt_data["email"],
            gender=GenderEnum(mt_data["gender"]),
            caste=CasteEnum(mt_data["caste"]),
            hashed_password=hash_password("Pass@1234"),
            role=RoleEnum.master_trainer,
            division_id=div.id,
            districts=mt_data["districts"],
            is_active=True,
            must_change_password=True,
        )
        db.add(mt)
    db.commit()

    district_to_div = {d: dn for dn, ds in DIVISION_DISTRICTS.items() for d in ds}

    rng = random.Random(42)
    schools_created = []
    for i, (udise, atl, sname, district, pin) in enumerate(SCHOOL_DATA):
        div = divs[district_to_div[district]]
        tname, temail_prefix, tgender, tcaste = TRAINER_DATA[i]
        pname, pemail_prefix = PRINCIPAL_DATA[i]

        school = School(
            udise_code=udise, atl_lab_code=atl, name=sname,
            district=district, pin_code=pin, state="Karnataka",
            division_id=div.id,
            school_type=SchoolTypeEnum.government,
            lab_type=LabTypeEnum.atl,
            education_type=EducationTypeEnum.secondary,
            max_grade=10,
            principal_name=pname,
            principal_email=f"{pemail_prefix}@ghs.edu.in",
            principal_phone=f"+91 9{rng.randint(700000000, 799999999)}",
            lab_area_sqft=rng.choice([900, 1000, 1200, 1500]),
            lab_launch_date=date(2022, rng.randint(1, 12), rng.randint(1, 28)),
        )
        db.add(school)
        db.flush()

        trainer = User(
            name=tname, email=f"{temail_prefix}@gttc.gov.in",
            gender=GenderEnum(tgender), caste=CasteEnum(tcaste),
            hashed_password=hash_password("Pass@1234"),
            role=RoleEnum.atl_trainer, division_id=div.id,
            is_active=True, must_change_password=True,
        )
        db.add(trainer)
        db.flush()
        db.add(SchoolTrainer(school_id=school.id, user_id=trainer.id,
                             assigned_from=date(2022, 1, 1), is_current=True))

        principal = User(
            name=pname, email=f"{pemail_prefix}@ghs.edu.in",
            hashed_password=hash_password("Pass@1234"),
            role=RoleEnum.principal, division_id=div.id,
            is_active=True, must_change_password=True,
        )
        db.add(principal)
        db.flush()
        db.add(SchoolPrincipal(school_id=school.id, user_id=principal.id,
                               assigned_from=date(2022, 1, 1), is_current=True))

        schools_created.append(school)

    db.commit()

    # Seed reports as running YTD totals
    for school in schools_created:
        school_rng = random.Random(school.id * 7 + 13)
        months_data = _running_totals(school_rng)
        for m in months_data:
            report = MonthlyReport(
                school_id=school.id, submitted_by=admin_id,
                report_year=m["year"], report_month=m["month"],
                academic_year=m["acad"],
                students_school=m["students_school"],
                students_community=m["students_community"],
                students_girls=m["students_girls"],
                workshops_school=m["workshops_school"],
                workshops_community=m["workshops_community"],
                mentoring_school=m["mentoring_school"],
                mentoring_community=m["mentoring_community"],
                innovation_school=m["innovation_school"],
                innovation_community=m["innovation_community"],
                patents_school=m["patents_school"],
                patents_community=m["patents_community"],
                copyrights_school=m["copyrights_school"],
                copyrights_community=m["copyrights_community"],
                atl_competitions_participated=m["atl_competitions_participated"],
                atl_competitions_won=m["atl_competitions_won"],
                other_competitions_participated=m["other_competitions_participated"],
                other_competitions_won=m["other_competitions_won"],
                highlight_of_month=m["highlight"],
                status=ReportStatusEnum.submitted,
                submitted_at=date(m["year"], m["month"], school_rng.randint(5, 14)),
            )
            db.add(report)

    db.commit()
