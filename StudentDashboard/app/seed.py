from datetime import date
import random

import bcrypt
from sqlalchemy import func

from app.models import Account, School, Trainer


DEFAULT_TRAINER_PASSWORD = "Trainer@123"


DIVISION_DISTRICTS = {
    "Bengaluru": ["Bengaluru South", "Bengaluru North", "Tumkur"],
    "Belagavi": ["Belagavi", "Dharwad", "Vijayapura"],
    "Mysuru": ["Mysore", "Hassan", "Udupi"],
    "Kalburgi": ["Kalburgi", "Raichur", "Bidar"],
}

MASTER_TRAINERS = [
    {
        "name": "Amit Kumar",
        "email": "amit.kumar@gttc.gov.in",
        "division": "Bengaluru",
        "gender": "male",
        "caste": "cat_1",
        "districts": ["Bengaluru South", "Bengaluru North", "Tumkur"],
    },
    {
        "name": "Rajesh Patil",
        "email": "rajesh.patil@gttc.gov.in",
        "division": "Belagavi",
        "gender": "male",
        "caste": "cat_3a",
        "districts": ["Belagavi", "Dharwad", "Vijayapura"],
    },
    {
        "name": "Mohan Gowda",
        "email": "mohan.gowda@gttc.gov.in",
        "division": "Mysuru",
        "gender": "male",
        "caste": "sc",
        "districts": ["Mysore", "Hassan", "Udupi"],
    },
    {
        "name": "Sunil Reddy",
        "email": "sunil.reddy@gttc.gov.in",
        "division": "Kalburgi",
        "gender": "male",
        "caste": "st",
        "districts": ["Kalburgi", "Raichur", "Bidar"],
    },
]

SCHOOL_DATA = [
    ("29010001001", "ATL-KA-001", "GHS Jayanagar", "Bengaluru South", "560041"),
    ("29010001002", "ATL-KA-002", "GHS Yelahanka", "Bengaluru North", "560064"),
    ("29020002001", "ATL-KA-003", "GHS Belagavi City", "Belagavi", "590001"),
    ("29020002002", "ATL-KA-004", "GHS Dharwad", "Dharwad", "580001"),
    ("29030003001", "ATL-KA-005", "GGHS Saraswathipuram", "Mysore", "570009"),
    ("29030003002", "ATL-KA-006", "GHS Hassan", "Hassan", "573201"),
    ("29040004001", "ATL-KA-007", "GHS Kalburgi North", "Kalburgi", "585101"),
    ("29040004002", "ATL-KA-008", "GHS Raichur", "Raichur", "584101"),
]

TRAINER_DATA = [
    ("Suresh Muthu", "suresh.muthu", "male", "sc"),
    ("Kavitha Reddy", "kavitha.reddy", "female", "cat_2a"),
    ("Rajesh Naik", "rajesh.naik", "male", "cat_3a"),
    ("Priya Sharma", "priya.sharma", "female", "cat_1"),
    ("Anil Gowda", "anil.gowda", "male", "cat_2b"),
    ("Meena Nair", "meena.nair", "female", "other"),
    ("Vinod Kumar", "vinod.kumar", "male", "cat_1"),
    ("Suma Joshi", "suma.joshi", "female", "sc"),
]

PRINCIPAL_DATA = [
    ("Dr. Ramesh M", "p.ramesh.m"),
    ("Mrs. Sudha K", "p.sudha.k"),
    ("Mr. Nagesh R", "p.nagesh.r"),
    ("Dr. Anand S", "p.anand.s"),
    ("Mrs. Latha C", "p.latha.c"),
    ("Dr. Kishore P", "p.kishore.p"),
    ("Mr. Sanjay T", "p.sanjay.t"),
    ("Mrs. Geetha N", "p.geetha.n"),
]


def _district_to_division():
    return {district: division for division, districts in DIVISION_DISTRICTS.items() for district in districts}


def _latest_student_counts(seed_value: int):
    rng = random.Random(seed_value)
    students = rng.randint(60, 130)
    girls = rng.randint(20, students // 2)
    for month_index in range(5):
        if month_index > 0 and rng.random() < 0.25:
            students += rng.randint(5, 20)
            girls += rng.randint(2, 8)
            girls = min(girls, students // 2)
        if month_index > 0 and rng.random() < 0.15:
            rng.randint(5, 15)
        rng.randint(1, 4)
        rng.randint(1, 5)
        rng.randint(0, 3)
        rng.randint(0, 1)
        rng.randint(0, 1)
        rng.randint(0, 2)
        rng.randint(0, 1)
        rng.randint(0, 2)
        rng.randint(0, 1)
    return students, girls


def seed_initial_data(db):
    if db.query(School).first() or db.query(Trainer).first():
        return

    district_to_division = _district_to_division()

    for trainer in MASTER_TRAINERS:
        db.add(
            Trainer(
                name=trainer["name"],
                email=trainer["email"],
                role="master_trainer",
                gender=trainer["gender"],
                caste=trainer["caste"],
                division=trainer["division"],
                districts=", ".join(trainer["districts"]),
                specialization="Master trainer",
            )
        )

    rng = random.Random(42)
    for index, (udise, atl_code, school_name, district, pin_code) in enumerate(SCHOOL_DATA):
        division = district_to_division[district]
        trainer_name, trainer_email_prefix, trainer_gender, trainer_caste = TRAINER_DATA[index]
        principal_name, principal_email_prefix = PRINCIPAL_DATA[index]
        current_students, girls_count = _latest_student_counts((index + 1) * 7 + 13)

        db.add(
            Trainer(
                name=trainer_name,
                email=f"{trainer_email_prefix}@gttc.gov.in",
                role="atl_trainer",
                gender=trainer_gender,
                caste=trainer_caste,
                division=division,
                districts=district,
                assigned_school=school_name,
                specialization="ATL trainer",
            )
        )

        db.add(
            School(
                udise_code=udise,
                atl_lab_code=atl_code,
                name=school_name,
                district=district,
                division=division,
                state="Karnataka",
                pin_code=pin_code,
                school_type="government",
                lab_type="atl",
                education_type="secondary",
                max_grade=10,
                principal_name=principal_name,
                principal_email=f"{principal_email_prefix}@ghs.edu.in",
                principal_phone=f"+91 9{rng.randint(700000000, 799999999)}",
                lab_area_sqft=rng.choice([900, 1000, 1200, 1500]),
                lab_launch_date=date(2022, rng.randint(1, 12), rng.randint(1, 28)),
                assigned_trainer=trainer_name,
                current_students=current_students,
                girls_count=girls_count,
            )
        )

    db.commit()


def _hash_password(password: str):
    return bcrypt.hashpw(password[:72].encode(), bcrypt.gensalt()).decode()


def seed_trainer_accounts(db):
    trainers = db.query(Trainer).all()
    if not trainers:
        return

    hashed_password = _hash_password(DEFAULT_TRAINER_PASSWORD)

    for trainer in trainers:
        normalized_email = trainer.email.strip().lower()
        account = db.query(Account).filter(func.lower(Account.email) == normalized_email).first()
        if account:
            account.name = trainer.name
            account.role = "trainer"
            account.hashed_password = hashed_password
            continue

        db.add(
            Account(
                name=trainer.name,
                email=normalized_email,
                role="trainer",
                hashed_password=hashed_password,
            )
        )

    db.commit()
