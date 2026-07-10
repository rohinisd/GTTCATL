import math
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.attendance import TrainerAttendance
from app.models.hierarchy import School, SchoolTrainer
from app.models.users import User, RoleEnum
from app.models.leave import LeaveRequest, Holiday, LeaveStatusEnum
from app.core.security import require_any, require_state_admin, get_current_user
from app.core.timezone import now_ist, today_ist

router = APIRouter()


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _day_off_reason(db: Session, user, school, day) -> Optional[str]:
    """Return a human message if `day` is a holiday or approved-leave day for the
    trainer (so check-in is unnecessary / blocked); otherwise None."""
    # Holiday — applies to the whole division (or all divisions when division_id is null)
    hol = db.query(Holiday).filter(
        Holiday.date == day,
        ((Holiday.division_id == None) | (Holiday.division_id == school.division_id)),
    ).first()
    if hol:
        return f"{day.isoformat()} is a holiday ({hol.name}). Attendance is not required."
    # Approved leave covering this day
    lv = db.query(LeaveRequest).filter(
        LeaveRequest.user_id == user.id,
        LeaveRequest.status  == LeaveStatusEnum.approved,
        LeaveRequest.from_date <= day,
        LeaveRequest.to_date   >= day,
    ).first()
    if lv:
        return "You are on approved leave today. Attendance is not required."
    return None


def _fmt_record(r: TrainerAttendance) -> dict:
    return {
        "id":             r.id,
        "user_id":        r.user_id,
        "user_name":      r.user.name  if r.user   else None,
        "school_id":      r.school_id,
        "school_name":    r.school.name if r.school else None,
        "date":           r.date.isoformat(),
        "check_in_at":    r.check_in_at.isoformat()  if r.check_in_at  else None,
        "check_out_at":   r.check_out_at.isoformat() if r.check_out_at else None,
        "check_in_lat":   r.check_in_lat,
        "check_in_lng":   r.check_in_lng,
        "check_out_lat":  r.check_out_lat,
        "check_out_lng":  r.check_out_lng,
        "check_in_dist":  round(r.check_in_dist,  1) if r.check_in_dist  is not None else None,
        "check_out_dist": round(r.check_out_dist, 1) if r.check_out_dist is not None else None,
        "in_geofence":    r.in_geofence,
        "notes":          r.notes,
        "marked_by":      r.marked_by,
        "school_lat":     r.school.geo_latitude  if r.school else None,
        "school_lng":     r.school.geo_longitude if r.school else None,
        "school_radius":  r.school.geo_radius    if r.school else None,
    }


# ── Geofence management ─────────────────────────────────────────────────────

@router.get("/school-geofence/{school_id}")
def get_school_geofence(
    school_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_any),
):
    s = db.query(School).filter(School.id == school_id).first()
    if not s:
        raise HTTPException(404, "School not found")
    return {
        "school_id":  s.id,
        "name":       s.name,
        "latitude":   s.geo_latitude,
        "longitude":  s.geo_longitude,
        "radius":     s.geo_radius or 200,
    }


@router.patch("/school-geofence/{school_id}")
def set_school_geofence(
    school_id: int,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role not in (RoleEnum.state_admin, RoleEnum.division_master):
        raise HTTPException(403, "Only admin/division master can set geofence")
    s = db.query(School).filter(School.id == school_id).first()
    if not s:
        raise HTTPException(404, "School not found")
    if "latitude"  in body and body["latitude"]  is not None: s.geo_latitude  = float(body["latitude"])
    if "longitude" in body and body["longitude"] is not None: s.geo_longitude = float(body["longitude"])
    if "radius"    in body and body["radius"]    is not None: s.geo_radius    = int(body["radius"])
    db.commit()
    return {"ok": True, "latitude": s.geo_latitude, "longitude": s.geo_longitude, "radius": s.geo_radius}


# ── Trainer check-in / check-out ─────────────────────────────────────────────

@router.post("/checkin")
def check_in(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_any),
):
    if current_user.role != RoleEnum.atl_trainer:
        raise HTTPException(403, "Only ATL trainers can record attendance")

    lat = body.get("latitude")
    lng = body.get("longitude")
    if lat is None or lng is None:
        raise HTTPException(400, "latitude and longitude are required")

    school_id_req = body.get("school_id")
    if school_id_req:
        # Verify the trainer is actually assigned to this school
        link = db.query(SchoolTrainer).filter(
            SchoolTrainer.user_id == current_user.id,
            SchoolTrainer.school_id == school_id_req,
            SchoolTrainer.is_current == True,
        ).first()
        if not link:
            raise HTTPException(400, "You are not assigned to this school")
        school = db.query(School).filter(School.id == school_id_req).first()
    else:
        # Fall back to first assignment (single-school trainers)
        link = db.query(SchoolTrainer).filter(
            SchoolTrainer.user_id == current_user.id,
            SchoolTrainer.is_current == True,
        ).first()
        if not link:
            raise HTTPException(400, "No school assigned to this trainer")
        school = db.query(School).filter(School.id == link.school_id).first()

    if not school:
        raise HTTPException(400, "Assigned school not found")

    today = today_ist()

    # Block check-in on holidays / approved leave (no login needed those days)
    blocked = _day_off_reason(db, current_user, school, today)
    if blocked:
        raise HTTPException(400, blocked)

    # Prevent duplicate check-in for same day
    existing = db.query(TrainerAttendance).filter(
        TrainerAttendance.user_id   == current_user.id,
        TrainerAttendance.school_id == school.id,
        TrainerAttendance.date      == today,
    ).first()
    if existing and existing.check_in_at:
        raise HTTPException(400, "Already checked in today")

    # Calculate distance from school and enforce geofence
    distance = None
    in_geofence = True
    if school.geo_latitude and school.geo_longitude:
        distance = _haversine(lat, lng, school.geo_latitude, school.geo_longitude)
        radius = school.geo_radius or 200
        in_geofence = distance <= radius
        if not in_geofence:
            raise HTTPException(
                400,
                f"You are {round(distance)}m away from school. "
                f"Must be within {radius}m to check in.",
            )

    if existing:
        existing.check_in_at   = now_ist()
        existing.check_in_lat  = lat
        existing.check_in_lng  = lng
        existing.check_in_dist = distance
        existing.in_geofence   = in_geofence
        record = existing
    else:
        record = TrainerAttendance(
            user_id       = current_user.id,
            school_id     = school.id,
            date          = today,
            check_in_at   = now_ist(),
            check_in_lat  = lat,
            check_in_lng  = lng,
            check_in_dist = distance,
            in_geofence   = in_geofence,
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return {
        "ok":          True,
        "id":          record.id,
        "in_geofence": record.in_geofence,
        "distance":    round(distance, 1) if distance is not None else None,
        "radius":      school.geo_radius,
        "school_has_location": bool(school.geo_latitude and school.geo_longitude),
    }


@router.post("/checkout")
def check_out(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_any),
):
    if current_user.role != RoleEnum.atl_trainer:
        raise HTTPException(403, "Only ATL trainers can record attendance")

    lat = body.get("latitude")
    lng = body.get("longitude")
    if lat is None or lng is None:
        raise HTTPException(400, "latitude and longitude are required")

    today = today_ist()
    school_id_req = body.get("school_id")
    if school_id_req:
        record = db.query(TrainerAttendance).filter(
            TrainerAttendance.user_id   == current_user.id,
            TrainerAttendance.school_id == school_id_req,
            TrainerAttendance.date      == today,
        ).first()
    else:
        record = db.query(TrainerAttendance).filter(
            TrainerAttendance.user_id == current_user.id,
            TrainerAttendance.date   == today,
        ).first()
    if not record or not record.check_in_at:
        raise HTTPException(400, "Please check in first")
    if record.check_out_at:
        raise HTTPException(400, "Already checked out today")

    school = db.query(School).filter(School.id == record.school_id).first()
    distance = None
    if school and school.geo_latitude and school.geo_longitude:
        distance = _haversine(lat, lng, school.geo_latitude, school.geo_longitude)
        radius = school.geo_radius or 200
        if distance > radius:
            raise HTTPException(
                400,
                f"You are {round(distance)}m away from school. "
                f"Must be within {radius}m to check out.",
            )

    record.check_out_at   = now_ist()
    record.check_out_lat  = lat
    record.check_out_lng  = lng
    record.check_out_dist = distance
    db.commit()
    db.refresh(record)
    return {
        "ok":       True,
        "id":       record.id,
        "distance": round(distance, 1) if distance is not None else None,
    }


# ── Trainer self-service queries ─────────────────────────────────────────────

@router.get("/today")
def get_today(
    db: Session = Depends(get_db),
    current_user=Depends(require_any),
):
    today = today_ist()

    if current_user.role != RoleEnum.atl_trainer:
        record = db.query(TrainerAttendance).filter(
            TrainerAttendance.user_id == current_user.id,
            TrainerAttendance.date   == today,
        ).first()
        r = _fmt_record(record) if record else None
        status = ("checked_out" if record and record.check_out_at
                  else "checked_in" if record and record.check_in_at
                  else "absent")
        return {"status": status, "record": r, "day_off": None, "schools": []}

    # ATL trainers: return a per-school status list
    links = db.query(SchoolTrainer).filter(
        SchoolTrainer.user_id == current_user.id,
        SchoolTrainer.is_current == True,
    ).all()

    schools_data = []
    for link in links:
        school = db.query(School).filter(School.id == link.school_id).first()
        if not school:
            continue
        day_off = _day_off_reason(db, current_user, school, today)
        record = db.query(TrainerAttendance).filter(
            TrainerAttendance.user_id   == current_user.id,
            TrainerAttendance.school_id == school.id,
            TrainerAttendance.date      == today,
        ).first()
        r = _fmt_record(record) if record else None
        if r:
            status = ("checked_out" if record.check_out_at
                      else "checked_in" if record.check_in_at
                      else "absent")
        else:
            status = "day_off" if day_off else "absent"
        schools_data.append({
            "school_id":   school.id,
            "school_name": school.name,
            "status":      status,
            "record":      r,
            "day_off":     day_off,
        })

    # Legacy top-level fields (first school) for any older code paths
    first = schools_data[0] if schools_data else None
    return {
        "schools": schools_data,
        "status":  first["status"]  if first else "absent",
        "record":  first["record"]  if first else None,
        "day_off": first["day_off"] if first else None,
    }


@router.get("/history")
def trainer_history(
    from_date: Optional[str] = Query(None),
    to_date:   Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(require_any),
):
    q = db.query(TrainerAttendance).filter(
        TrainerAttendance.user_id == current_user.id
    )
    if from_date:
        q = q.filter(TrainerAttendance.date >= date.fromisoformat(from_date))
    if to_date:
        q = q.filter(TrainerAttendance.date <= date.fromisoformat(to_date))
    records = q.order_by(TrainerAttendance.date.desc()).offset(skip).limit(limit).all()
    return [_fmt_record(r) for r in records]


# ── Admin / master view ───────────────────────────────────────────────────────

@router.get("/records")
def list_records(
    school_id:  Optional[int] = Query(None),
    user_id:    Optional[int] = Query(None),
    division_id: Optional[int] = Query(None),
    district: Optional[str] = Query(None),
    from_date:  Optional[str] = Query(None),
    to_date:    Optional[str] = Query(None),
    in_geofence: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(require_any),
):
    if current_user.role == RoleEnum.atl_trainer:
        raise HTTPException(403, "Use /history for your own records")

    q = db.query(TrainerAttendance)

    # Scope: master_trainer sees only their districts' schools
    if current_user.role == RoleEnum.master_trainer:
        districts = current_user.districts or []
        if districts:
            school_ids = [s.id for s in db.query(School.id).filter(School.district.in_(districts)).all()]
            q = q.filter(TrainerAttendance.school_id.in_(school_ids))
        else:
            q = q.filter(False)
    elif current_user.role == RoleEnum.division_master:
        school_ids = [s.id for s in db.query(School.id).filter(
            School.division_id == current_user.division_id).all()]
        q = q.filter(TrainerAttendance.school_id.in_(school_ids))

    if school_id:   q = q.filter(TrainerAttendance.school_id == school_id)
    if user_id:     q = q.filter(TrainerAttendance.user_id   == user_id)
    if from_date:   q = q.filter(TrainerAttendance.date >= date.fromisoformat(from_date))
    if to_date:     q = q.filter(TrainerAttendance.date <= date.fromisoformat(to_date))
    if in_geofence is not None:
        q = q.filter(TrainerAttendance.in_geofence == in_geofence)
    if division_id is not None or district:
        school_q = db.query(School.id).filter(School.is_active == True)
        if division_id is not None:
            school_q = school_q.filter(School.division_id == division_id)
        if district:
            school_q = school_q.filter(School.district.ilike(f"%{district}%"))
        school_ids = [s.id for s in school_q.all()]
        q = q.filter(TrainerAttendance.school_id.in_(school_ids)) if school_ids else q.filter(False)

    records = q.order_by(TrainerAttendance.date.desc()).offset(skip).limit(limit).all()
    return [_fmt_record(r) for r in records]


# ── Admin manual mark ─────────────────────────────────────────────────────────

@router.patch("/{record_id}/manual")
def manual_mark(
    record_id: int,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role not in (RoleEnum.state_admin, RoleEnum.division_master, RoleEnum.master_trainer):
        raise HTTPException(403, "Not authorised")
    r = db.query(TrainerAttendance).filter(TrainerAttendance.id == record_id).first()
    if not r:
        raise HTTPException(404, "Record not found")
    if "notes"     in body: r.notes      = body["notes"]
    if "in_geofence" in body: r.in_geofence = bool(body["in_geofence"])
    r.marked_by = current_user.id
    db.commit()
    return {"ok": True}


@router.post("/manual-entry")
def manual_entry(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role not in (RoleEnum.state_admin, RoleEnum.division_master, RoleEnum.master_trainer):
        raise HTTPException(403, "Not authorised")
    user_id   = body.get("user_id")
    school_id = body.get("school_id")
    entry_date = date.fromisoformat(body["date"])

    existing = db.query(TrainerAttendance).filter(
        TrainerAttendance.user_id   == user_id,
        TrainerAttendance.school_id == school_id,
        TrainerAttendance.date      == entry_date,
    ).first()
    if existing:
        existing.in_geofence = True
        existing.notes       = body.get("notes", "Manually marked by admin")
        existing.marked_by   = current_user.id
    else:
        record = TrainerAttendance(
            user_id     = user_id,
            school_id   = school_id,
            date        = entry_date,
            in_geofence = True,
            notes       = body.get("notes", "Manually marked by admin"),
            marked_by   = current_user.id,
        )
        db.add(record)
    db.commit()
    return {"ok": True}
