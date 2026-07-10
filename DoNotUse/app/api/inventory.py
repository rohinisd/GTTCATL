"""Inventory requests workflow.

Trainers (ATL trainer / principal) submit requests for inventory items.
SPD (state_admin) — or a Division Master — reviews, approves, rejects, fulfils.
On approve, the approved quantity is added to the school's equipment_inventory.
Notifications are created at every status change so the requester sees progress.
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.users import User, RoleEnum, ActivityLog
from app.models.hierarchy import School, SchoolTrainer, SchoolPrincipal
from app.models.reports import (
    InventoryRequest, EquipmentInventory, Notification,
    Project, ProjectItem, ReportProjectUsage, MonthlyReport,
    ReportUsedItem, ReportBrokenItem,
    EquipmentInspection, InspectionItem,
)
from app.core.security import require_any, require_state_admin
from sqlalchemy import func

router = APIRouter()

ALLOWED_URGENCY = {"low", "medium", "high"}


# ─── helpers ─────────────────────────────────────────────────────────────
def _trainer_school_ids(db: Session, user: User) -> list[int]:
    """Schools this user is allowed to act on (atl_trainer / principal)."""
    if user.role == RoleEnum.atl_trainer:
        return [st.school_id for st in db.query(SchoolTrainer).filter(
            SchoolTrainer.user_id == user.id, SchoolTrainer.is_current == True
        ).all()]
    if user.role == RoleEnum.principal:
        return [sp.school_id for sp in db.query(SchoolPrincipal).filter(
            SchoolPrincipal.user_id == user.id, SchoolPrincipal.is_current == True
        ).all()]
    return []


def _can_review(user: User) -> bool:
    return user.role in (RoleEnum.state_admin, RoleEnum.division_master)


def _serialise(r: InventoryRequest) -> dict:
    return {
        "id": r.id,
        "school_id": r.school_id,
        "school_name": r.school.name if r.school else None,
        "district": r.school.district if r.school else None,
        "item_id": r.item_id,
        "item_name": r.item_name,
        "item_desc": r.item_desc,
        "is_new_item": bool(r.is_new_item),
        "requested_qty": r.requested_qty,
        "approved_qty": r.approved_qty,
        "reason": r.reason,
        "urgency": r.urgency,
        "status": r.status,
        "rejection_reason": r.rejection_reason,
        "requested_by": r.requested_by,
        "requester_name": r.requester.name if r.requester else None,
        "reviewed_by": r.reviewed_by,
        "reviewer_name": r.reviewer.name if r.reviewer else None,
        "reviewed_at": r.reviewed_at,
        "fulfilled_at": r.fulfilled_at,
        "created_at": r.created_at,
    }


def _notify(db: Session, user_id: int, title: str, body: str, link_page: str = "inventory"):
    if not user_id:
        return
    db.add(Notification(
        user_id=user_id, title=title, body=body,
        notif_type="inventory_request", link_page=link_page,
    ))


# ─── endpoints ──────────────────────────────────────────────────────────

@router.post("/requests")
def submit_request(
    body: dict = Body(...),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """ATL trainer / principal submits a new request for their school."""
    if current_user.role not in (RoleEnum.atl_trainer, RoleEnum.principal):
        raise HTTPException(403, "Only ATL trainers and principals can submit requests")

    school_id = body.get("school_id")
    if not school_id:
        raise HTTPException(400, "school_id is required")
    allowed = _trainer_school_ids(db, current_user)
    if school_id not in allowed:
        raise HTTPException(403, "You can only request for your assigned school(s)")

    item_id = body.get("item_id")               # may be None
    item_name = (body.get("item_name") or "").strip()
    if not item_name:
        raise HTTPException(400, "item_name is required")
    item_desc = (body.get("item_desc") or "").strip() or None
    is_new_item = bool(body.get("is_new_item") or not item_id)

    try:
        qty = int(body.get("requested_qty"))
    except (TypeError, ValueError):
        raise HTTPException(400, "requested_qty must be an integer")
    if qty <= 0:
        raise HTTPException(400, "Quantity must be greater than 0")

    reason = (body.get("reason") or "").strip()
    if len(reason) < 20:
        raise HTTPException(400, "Reason must be at least 20 characters")

    urgency = (body.get("urgency") or "medium").lower()
    if urgency not in ALLOWED_URGENCY:
        urgency = "medium"

    # block duplicate pending request for the same school + item
    dup_q = db.query(InventoryRequest).filter(
        InventoryRequest.school_id == school_id,
        InventoryRequest.status == "pending",
    )
    if item_id:
        dup_q = dup_q.filter(InventoryRequest.item_id == item_id)
    else:
        dup_q = dup_q.filter(InventoryRequest.item_name.ilike(item_name))
    if dup_q.first():
        raise HTTPException(409, "You already have a pending request for this item. Wait for SPD review.")

    # if item_id given, sanity-check it belongs to the same school
    if item_id:
        item = db.query(EquipmentInventory).filter(EquipmentInventory.id == item_id).first()
        if not item or item.school_id != school_id:
            item_id = None
            is_new_item = True

    req = InventoryRequest(
        school_id=school_id, item_id=item_id, item_name=item_name, item_desc=item_desc,
        is_new_item=is_new_item, requested_qty=qty, reason=reason, urgency=urgency,
        status="pending", requested_by=current_user.id,
    )
    db.add(req); db.commit(); db.refresh(req)

    db.add(ActivityLog(
        user_id=current_user.id, action="Submitted inventory request",
        model_type="InventoryRequest", model_id=req.id,
        description=f"{qty} × {item_name} ({urgency})",
    ))
    db.commit()
    return _serialise(req)


@router.get("/requests")
def list_requests(
    status: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    school_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),       # search by school or item name
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """Reviewers (SPD / Division Master) see all; trainers see their school's only."""
    query = db.query(InventoryRequest)
    if not _can_review(current_user):
        ids = _trainer_school_ids(db, current_user)
        if not ids:
            return []
        query = query.filter(InventoryRequest.school_id.in_(ids))

    if status:   query = query.filter(InventoryRequest.status == status)
    if urgency:  query = query.filter(InventoryRequest.urgency == urgency)
    if school_id and _can_review(current_user):
        query = query.filter(InventoryRequest.school_id == school_id)
    if q:
        like = f"%{q}%"
        query = query.outerjoin(School).filter(or_(
            InventoryRequest.item_name.ilike(like),
            School.name.ilike(like),
        ))

    # high urgency first, then newest
    rows = query.order_by(
        InventoryRequest.status == "pending",  # SQLite: True>False, so pending first when desc
        InventoryRequest.urgency.desc(),       # high>medium>low alphabetically? no — handle in code
        InventoryRequest.created_at.desc(),
    ).limit(500).all()

    # client-side urgency ordering for the result set
    weight = {"high": 0, "medium": 1, "low": 2}
    rows.sort(key=lambda r: (
        0 if r.status == "pending" else 1,
        weight.get(r.urgency, 1),
        -(r.created_at.timestamp() if r.created_at else 0),
    ))
    return [_serialise(r) for r in rows]


@router.get("/requests/mine")
def my_requests(
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """Convenience endpoint — current user's submitted requests."""
    rows = (db.query(InventoryRequest)
            .filter(InventoryRequest.requested_by == current_user.id)
            .order_by(InventoryRequest.created_at.desc()).all())
    return [_serialise(r) for r in rows]


@router.get("/requests/pending-count")
def pending_count(
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """Used by the sidebar badge. Reviewers see global count; trainers see theirs."""
    q = db.query(InventoryRequest).filter(InventoryRequest.status == "pending")
    if not _can_review(current_user):
        ids = _trainer_school_ids(db, current_user)
        if not ids:
            return {"count": 0}
        q = q.filter(InventoryRequest.school_id.in_(ids))
    return {"count": q.count()}


@router.post("/requests/{req_id}/approve")
def approve_request(
    req_id: int, body: dict = Body(...),
    db: Session = Depends(get_db), current_user=Depends(require_state_admin),
):
    """SPD approves: adds approved_qty to the school's equipment inventory and notifies."""
    r = db.query(InventoryRequest).filter(InventoryRequest.id == req_id).first()
    if not r:
        raise HTTPException(404, "Request not found")
    if r.status != "pending":
        raise HTTPException(400, "Request already processed")
    if r.is_new_item and not r.item_id:
        # spec rule: new-item requests need the item created first; we allow it but
        # create a fresh equipment_inventory entry for the school here.
        pass

    try:
        approved_qty = int(body.get("approved_qty", r.requested_qty))
    except (TypeError, ValueError):
        raise HTTPException(400, "approved_qty must be an integer")
    if approved_qty <= 0:
        raise HTTPException(400, "approved_qty must be greater than 0")

    # Apply to the school's equipment_inventory
    if r.item_id:
        item = db.query(EquipmentInventory).filter(EquipmentInventory.id == r.item_id).first()
        if item:
            item.quantity = (item.quantity or 0) + approved_qty
        else:
            r.item_id = None  # row went missing — fall through to create-new
    if not r.item_id:
        new_item = EquipmentInventory(
            school_id=r.school_id, item_name=r.item_name,
            quantity=approved_qty, condition="good",
            notes=r.item_desc, added_by=current_user.id,
        )
        db.add(new_item); db.flush()
        r.item_id = new_item.id

    r.status = "approved"
    r.approved_qty = approved_qty
    r.reviewed_by = current_user.id
    r.reviewed_at = datetime.now(timezone.utc)

    partial = approved_qty < r.requested_qty
    body_msg = (f"{approved_qty} of {r.requested_qty} {r.item_name} approved by {current_user.name}."
                if partial else
                f"{approved_qty} × {r.item_name} approved by {current_user.name}.")
    _notify(db, r.requested_by, "Inventory request approved", body_msg)

    db.add(ActivityLog(
        user_id=current_user.id, action="Approved inventory request",
        model_type="InventoryRequest", model_id=r.id,
        description=f"{approved_qty} × {r.item_name} → school #{r.school_id}",
    ))
    db.commit()
    return _serialise(r)


@router.post("/requests/{req_id}/reject")
def reject_request(
    req_id: int, body: dict = Body(...),
    db: Session = Depends(get_db), current_user=Depends(require_state_admin),
):
    r = db.query(InventoryRequest).filter(InventoryRequest.id == req_id).first()
    if not r:
        raise HTTPException(404, "Request not found")
    if r.status != "pending":
        raise HTTPException(400, "Request already processed")

    reason = (body.get("rejection_reason") or "").strip()
    if len(reason) < 10:
        raise HTTPException(400, "Rejection reason must be at least 10 characters")

    r.status = "rejected"
    r.rejection_reason = reason
    r.reviewed_by = current_user.id
    r.reviewed_at = datetime.now(timezone.utc)

    _notify(db, r.requested_by, "Inventory request rejected",
            f"Your request for {r.requested_qty} × {r.item_name} was not approved. Reason: {reason}")

    db.add(ActivityLog(
        user_id=current_user.id, action="Rejected inventory request",
        model_type="InventoryRequest", model_id=r.id, description=reason,
    ))
    db.commit()
    return _serialise(r)


@router.post("/requests/{req_id}/fulfill")
def fulfill_request(
    req_id: int,
    db: Session = Depends(get_db), current_user=Depends(require_state_admin),
):
    """SPD clicks this when items have physically shipped."""
    r = db.query(InventoryRequest).filter(InventoryRequest.id == req_id).first()
    if not r:
        raise HTTPException(404, "Request not found")
    if r.status != "approved":
        raise HTTPException(400, "Only approved requests can be marked fulfilled")

    r.status = "fulfilled"
    r.fulfilled_at = datetime.now(timezone.utc)

    _notify(db, r.requested_by, "Inventory shipped",
            f"{r.approved_qty} × {r.item_name} have been dispatched to your school.")
    db.commit()
    return _serialise(r)


# ─── helper: a school's inventory (so the trainer can "Request more" of one) ──
def _equip_dict(e: EquipmentInventory) -> dict:
    return {
        "id": e.id, "item_name": e.item_name, "quantity": e.quantity,
        "condition": e.condition, "last_checked": e.last_checked, "notes": e.notes,
        "issued_at": e.issued_at,
        "working_qty": e.working_qty, "not_working_qty": e.not_working_qty,
        "additional_required": e.additional_required, "review_notes": e.review_notes,
        "reviewed_at": e.reviewed_at,
        "reviewer_name": e.reviewer.name if e.reviewer else None,
        "reviewed": e.reviewed_at is not None,
    }


@router.get("/schools/{school_id}/inventory")
def school_inventory(
    school_id: int,
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """Returns the school's equipment_inventory list. Trainers limited to their own."""
    if not _can_review(current_user):
        if school_id not in _trainer_school_ids(db, current_user):
            raise HTTPException(403, "Not your school")
    rows = (db.query(EquipmentInventory)
            .filter(EquipmentInventory.school_id == school_id)
            .order_by(EquipmentInventory.item_name).all())
    return [_equip_dict(e) for e in rows]


# ═══════════════════════════════════════════════════════════════════════════
#  EQUIPMENT ISSUANCE (SPD → schools)  +  CONDITION REVIEW (ATL trainer)
#  SPD issues equipment to a school / a whole division / all schools, with
#  quantities. The issued list lands in each school's inventory; that school's
#  ATL trainer then reviews each item: working / not-working / additional needed.
# ═══════════════════════════════════════════════════════════════════════════

def _school_trainer_user_ids(db: Session, school_id: int) -> list[int]:
    return [st.user_id for st in db.query(SchoolTrainer).filter(
        SchoolTrainer.school_id == school_id, SchoolTrainer.is_current == True).all()]


@router.post("/issue")
def issue_equipment(
    body: dict = Body(...),
    db: Session = Depends(get_db), current_user=Depends(require_state_admin),
):
    """SPD issues equipment to schools. Adds the given quantity to each target
    school's stock (creating the item row if absent) and notifies its trainers.

    body = {
      scope: 'school' | 'division' | 'all',
      school_id?: int,          # required when scope='school'
      division_id?: int,        # required when scope='division'
      items: [{ item_name, quantity }]
    }"""
    scope = (body.get("scope") or "").strip()
    items = body.get("items") or []
    if scope not in ("school", "division", "all"):
        raise HTTPException(400, "scope must be 'school', 'division' or 'all'")
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "At least one item is required")

    # clean items
    clean = []
    for it in items:
        name = (it.get("item_name") or "").strip()
        if not name:
            continue
        try:
            qty = int(it.get("quantity"))
        except (TypeError, ValueError):
            raise HTTPException(400, f"Quantity for '{name}' must be a whole number")
        if qty <= 0:
            raise HTTPException(400, f"Quantity for '{name}' must be greater than 0")
        clean.append((name, qty))
    if not clean:
        raise HTTPException(400, "At least one valid item is required")

    # resolve target schools
    q = db.query(School)
    if scope == "school":
        sid = body.get("school_id")
        if not sid:
            raise HTTPException(400, "school_id is required for scope='school'")
        q = q.filter(School.id == sid)
    elif scope == "division":
        did = body.get("division_id")
        if not did:
            raise HTTPException(400, "division_id is required for scope='division'")
        q = q.filter(School.division_id == did)
    schools = q.all()
    if not schools:
        raise HTTPException(404, "No schools match the selected scope")

    now = datetime.now(timezone.utc)
    notified = set()
    for school in schools:
        for name, qty in clean:
            row = (db.query(EquipmentInventory)
                   .filter(EquipmentInventory.school_id == school.id,
                           EquipmentInventory.item_name == name).first())
            if row:
                row.quantity = (row.quantity or 0) + qty
                row.issued_by = current_user.id
                row.issued_at = now
            else:
                db.add(EquipmentInventory(
                    school_id=school.id, item_name=name, quantity=qty,
                    condition="good", issued_by=current_user.id, issued_at=now,
                    added_by=current_user.id))
        # notify each trainer of this school once
        for uid in _school_trainer_user_ids(db, school.id):
            if uid not in notified:
                _notify(db, uid, "New equipment issued",
                        f"{len(clean)} equipment item(s) were issued to {school.name}. "
                        f"Please review their condition in My Inventory.",
                        link_page="inventory")
                notified.add(uid)

    db.add(ActivityLog(
        user_id=current_user.id, action="Issued equipment",
        model_type="EquipmentInventory", model_id=None,
        description=f"{len(clean)} item(s) → {len(schools)} school(s) (scope={scope})"))
    db.commit()
    return {"schools": len(schools), "items": len(clean),
            "school_names": [s.name for s in schools[:50]]}


@router.post("/schools/{school_id}/review")
def review_equipment(
    school_id: int, body: dict = Body(...),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """The school's ATL trainer reviews issued equipment: for each item records
    working / not-working counts and how many more are required.

    body = { items: [{ id, working_qty, not_working_qty, additional_required, review_notes? }] }"""
    # only the school's own trainer/principal (or a reviewer) may submit
    if not _can_review(current_user):
        if school_id not in _trainer_school_ids(db, current_user):
            raise HTTPException(403, "Not your school")

    rows = body.get("items") or []
    if not isinstance(rows, list) or not rows:
        raise HTTPException(400, "No review items supplied")

    now = datetime.now(timezone.utc)
    updated = 0
    for r in rows:
        item = (db.query(EquipmentInventory)
                .filter(EquipmentInventory.id == r.get("id"),
                        EquipmentInventory.school_id == school_id).first())
        if not item:
            continue

        def _int(v):
            try:
                n = int(v)
            except (TypeError, ValueError):
                return 0
            return max(0, n)

        working = _int(r.get("working_qty"))
        broken  = _int(r.get("not_working_qty"))
        need    = _int(r.get("additional_required"))
        if working + broken > (item.quantity or 0):
            raise HTTPException(400,
                f"'{item.item_name}': working + not-working ({working + broken}) "
                f"cannot exceed issued quantity ({item.quantity or 0})")

        item.working_qty = working
        item.not_working_qty = broken
        item.additional_required = need
        item.review_notes = (r.get("review_notes") or "").strip() or None
        item.condition = ("missing" if working == 0 and broken == 0 and (item.quantity or 0) > 0
                          else "damaged" if broken > 0 and broken >= working
                          else "good")
        item.last_checked = now.date()
        item.reviewed_by = current_user.id
        item.reviewed_at = now
        updated += 1

    if not updated:
        raise HTTPException(404, "None of the supplied items belong to this school")

    # notify reviewers (SPD) that a school finished its condition review
    school = db.query(School).filter(School.id == school_id).first()
    for admin in db.query(User).filter(User.role == RoleEnum.state_admin).all():
        _notify(db, admin.id, "Equipment review submitted",
                f"{school.name if school else 'A school'} reviewed {updated} equipment item(s).",
                link_page="issue")

    db.add(ActivityLog(
        user_id=current_user.id, action="Reviewed equipment condition",
        model_type="EquipmentInventory", model_id=school_id,
        description=f"{updated} item(s) reviewed for school #{school_id}"))
    db.commit()
    return {"updated": updated}


@router.get("/review-overview")
def review_overview(
    division_id: Optional[int] = Query(None),
    db: Session = Depends(get_db), current_user=Depends(require_state_admin),
):
    """Per-school summary for SPD: items issued, reviewed status, totals of
    not-working and additionally-required units."""
    sq = db.query(School)
    if division_id:
        sq = sq.filter(School.division_id == division_id)
    schools = sq.order_by(School.name).all()
    out = []
    for s in schools:
        rows = db.query(EquipmentInventory).filter(EquipmentInventory.school_id == s.id).all()
        if not rows:
            continue
        reviewed = sum(1 for r in rows if r.reviewed_at is not None)
        out.append({
            "school_id": s.id, "school_name": s.name,
            "district": s.district,
            "division_name": s.division.name if s.division else None,
            "total_items": len(rows),
            "reviewed_items": reviewed,
            "issued_qty": sum(r.quantity or 0 for r in rows),
            "working_qty": sum(r.working_qty or 0 for r in rows),
            "not_working_qty": sum(r.not_working_qty or 0 for r in rows),
            "additional_required": sum(r.additional_required or 0 for r in rows),
            "fully_reviewed": reviewed == len(rows),
        })
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  PROJECTS  —  SPD/GTTC creates monthly projects; ATL trainers select them in
#  their reports; the linked bill-of-materials drives item usage counts.
# ═══════════════════════════════════════════════════════════════════════════

def _project_dict(p: Project, with_items: bool = False, school_count: int = None) -> dict:
    d = {
        "id": p.id, "exp_no": p.exp_no, "name": p.name,
        "description": p.description, "is_active": bool(p.is_active),
        "target_year": p.target_year, "target_month": p.target_month,
        "academic_year": p.academic_year, "created_by": p.created_by,
        "created_at": p.created_at, "item_count": len(p.items),
    }
    if school_count is not None:
        d["school_count"] = school_count
    if with_items:
        d["items"] = [
            {"id": it.id, "item_name": it.item_name,
             "quantity": it.quantity, "qty_num": it.qty_num}
            for it in p.items
        ]
    return d


@router.post("/projects")
def create_project(
    body: dict = Body(...),
    db: Session = Depends(get_db), current_user=Depends(require_state_admin),
):
    """SPD/GTTC (state_admin) creates a project + its bill-of-materials.
    Becomes visible to all ATL trainers once active."""
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Project name is required")

    items = body.get("items") or []
    if not isinstance(items, list):
        raise HTTPException(400, "items must be a list")

    import re as _re
    def _qn(q):
        m = _re.search(r"\d+", q or "")
        return int(m.group()) if m else None

    p = Project(
        exp_no=body.get("exp_no"),
        name=name,
        description=(body.get("description") or "").strip() or None,
        is_active=bool(body.get("is_active", True)),
        target_year=body.get("target_year"),
        target_month=body.get("target_month"),
        academic_year=(body.get("academic_year") or None),
        created_by=current_user.id,
    )
    db.add(p)
    db.flush()
    for it in items:
        item_name = (it.get("item_name") or "").strip()
        if not item_name:
            continue
        qty = (it.get("quantity") or "").strip() or None
        db.add(ProjectItem(
            project_id=p.id, item_name=item_name, quantity=qty,
            qty_num=it.get("qty_num") if it.get("qty_num") is not None else _qn(qty),
        ))
    db.commit()
    db.refresh(p)
    return _project_dict(p, with_items=True)


@router.get("/projects")
def list_projects(
    active_only: bool = Query(False),
    academic_year: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    school_id: Optional[int] = Query(None),
    district: Optional[str] = Query(None),
    division_id: Optional[int] = Query(None),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """List projects. ATL trainers/principals only ever see active ones.
    Each project carries `school_count` = distinct schools that have selected it.
    Location filters (school/district/division) narrow to projects selected by
    that scope."""
    q = db.query(Project)
    if active_only or not _can_review(current_user):
        q = q.filter(Project.is_active == True)
    if academic_year:
        q = q.filter(Project.academic_year == academic_year)
    if month:
        q = q.filter(Project.target_month == month)

    # distinct-school count per project, scoped by location filter
    usage_q = (db.query(ReportProjectUsage.project_id,
                        func.count(func.distinct(ReportProjectUsage.school_id)))
               .join(School, School.id == ReportProjectUsage.school_id))
    if not _can_review(current_user):
        ids = _trainer_school_ids(db, current_user)
        usage_q = usage_q.filter(ReportProjectUsage.school_id.in_(ids or [-1]))
    if school_id:
        usage_q = usage_q.filter(ReportProjectUsage.school_id == school_id)
    if district:
        usage_q = usage_q.filter(School.district == district)
    if division_id:
        usage_q = usage_q.filter(School.division_id == division_id)
    count_map = dict(usage_q.group_by(ReportProjectUsage.project_id).all())

    rows = q.order_by(Project.exp_no.asc().nullslast(), Project.id.asc()).all()
    # when a location filter is active, only show projects selected within it
    if school_id or district or division_id:
        rows = [p for p in rows if count_map.get(p.id, 0) > 0]
    return [_project_dict(p, school_count=count_map.get(p.id, 0)) for p in rows]


@router.get("/projects/usage")
def project_item_usage(
    academic_year: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    school_id: Optional[int] = Query(None),
    district: Optional[str] = Query(None),
    division_id: Optional[int] = Query(None),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """Item usage count, aggregated across every project selected in reports.

    For each item: `selections` = number of report→project links whose project's
    BOM contains the item; `total_qty` = Σ qty_num over those selections (items
    with a non-numeric quantity like 'As required' are counted but not summed).
    Optionally scoped by School / District / Division. Also returns the list of
    schools (name · district · division) that contributed to the scope."""
    # always join School so we can scope/report by location
    rpu = db.query(ReportProjectUsage).join(
        School, School.id == ReportProjectUsage.school_id)

    # trainers only see their own schools
    if not _can_review(current_user):
        ids = _trainer_school_ids(db, current_user)
        rpu = rpu.filter(ReportProjectUsage.school_id.in_(ids or [-1]))
    if school_id:
        rpu = rpu.filter(ReportProjectUsage.school_id == school_id)
    if district:
        rpu = rpu.filter(School.district == district)
    if division_id:
        rpu = rpu.filter(School.division_id == division_id)

    # narrow by report period if requested
    if academic_year or month or year:
        rpu = rpu.join(MonthlyReport, MonthlyReport.id == ReportProjectUsage.report_id)
        if academic_year:
            rpu = rpu.filter(MonthlyReport.academic_year == academic_year)
        if month:
            rpu = rpu.filter(MonthlyReport.report_month == month)
        if year:
            rpu = rpu.filter(MonthlyReport.report_year == year)

    links = rpu.all()
    if not links:
        return {"items": [], "total_selections": 0, "schools": []}

    # count selections per project; collect schools in scope
    from collections import defaultdict
    proj_count: dict[int, int] = defaultdict(int)
    school_ids: set[int] = set()
    for l in links:
        proj_count[l.project_id] += 1
        if l.school_id:
            school_ids.add(l.school_id)

    # aggregate per item across the BOM of each selected project
    agg: dict[str, dict] = {}
    pitems = (db.query(ProjectItem)
              .filter(ProjectItem.project_id.in_(list(proj_count.keys()))).all())
    for it in pitems:
        n = proj_count.get(it.project_id, 0)
        if n == 0:
            continue
        key = it.item_name.strip().lower()
        slot = agg.setdefault(key, {
            "item_name": it.item_name, "selections": 0,
            "total_qty": 0, "has_numeric": False, "project_ids": set(),
        })
        slot["selections"] += n
        slot["project_ids"].add(it.project_id)
        if it.qty_num is not None:
            slot["total_qty"] += it.qty_num * n
            slot["has_numeric"] = True

    out = []
    for s in agg.values():
        out.append({
            "item_name": s["item_name"],
            "selections": s["selections"],
            "total_qty": s["total_qty"] if s["has_numeric"] else None,
            "project_count": len(s["project_ids"]),
        })
    out.sort(key=lambda x: (-(x["total_qty"] or 0), -x["selections"]))

    # schools that contributed (for display)
    schools = []
    if school_ids:
        srows = (db.query(School).filter(School.id.in_(school_ids))
                 .order_by(School.name).all())
        schools = [{
            "id": s.id, "name": s.name, "district": s.district,
            "division_id": s.division_id,
            "division_name": s.division.name if s.division else None,
        } for s in srows]

    return {"items": out, "total_selections": len(links), "schools": schools}


@router.get("/projects/{project_id}")
def get_project(
    project_id: int,
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(404, "Project not found")
    if not p.is_active and not _can_review(current_user):
        raise HTTPException(404, "Project not found")
    return _project_dict(p, with_items=True)


@router.get("/projects/{project_id}/schools")
def project_schools(
    project_id: int,
    academic_year: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """Schools (name · district · division) that have selected this project,
    with how many reports each linked it."""
    q = (db.query(School, func.count(ReportProjectUsage.id))
         .join(ReportProjectUsage, ReportProjectUsage.school_id == School.id)
         .filter(ReportProjectUsage.project_id == project_id))
    if not _can_review(current_user):
        ids = _trainer_school_ids(db, current_user)
        q = q.filter(School.id.in_(ids or [-1]))
    if academic_year or month:
        q = q.join(MonthlyReport, MonthlyReport.id == ReportProjectUsage.report_id)
        if academic_year:
            q = q.filter(MonthlyReport.academic_year == academic_year)
        if month:
            q = q.filter(MonthlyReport.report_month == month)
    rows = q.group_by(School.id).order_by(School.name).all()
    return [{
        "id": s.id, "name": s.name, "district": s.district,
        "division_id": s.division_id,
        "division_name": s.division.name if s.division else None,
        "times_selected": cnt,
    } for s, cnt in rows]


@router.patch("/projects/{project_id}")
def update_project(
    project_id: int,
    body: dict = Body(...),
    db: Session = Depends(get_db), current_user=Depends(require_state_admin),
):
    """SPD edits a project: toggle is_active, rename, retarget. Optionally
    replace the bill-of-materials by passing a new `items` list."""
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(404, "Project not found")

    if "name" in body:
        nm = (body.get("name") or "").strip()
        if nm:
            p.name = nm
    if "description" in body:
        p.description = (body.get("description") or "").strip() or None
    if "is_active" in body:
        p.is_active = bool(body["is_active"])
    for f in ("exp_no", "target_year", "target_month", "academic_year"):
        if f in body:
            setattr(p, f, body[f])

    if isinstance(body.get("items"), list):
        import re as _re
        def _qn(q):
            m = _re.search(r"\d+", q or "")
            return int(m.group()) if m else None
        db.query(ProjectItem).filter(ProjectItem.project_id == p.id).delete()
        for it in body["items"]:
            item_name = (it.get("item_name") or "").strip()
            if not item_name:
                continue
            qty = (it.get("quantity") or "").strip() or None
            db.add(ProjectItem(project_id=p.id, item_name=item_name,
                               quantity=qty, qty_num=_qn(qty)))
    db.commit()
    db.refresh(p)
    return _project_dict(p, with_items=True)


# ─── report ⇄ project linking (trainer selects projects in monthly report) ──

def _report_school_guard(db: Session, current_user: User, report: MonthlyReport):
    """A trainer/principal may only touch reports for their own school."""
    if _can_review(current_user):
        return
    if report.school_id not in _trainer_school_ids(db, current_user):
        raise HTTPException(403, "Not your school's report")


@router.post("/reports/{report_id}/projects")
def set_report_projects(
    report_id: int,
    body: dict = Body(...),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """Trainer selects the projects completed in this report. Replaces the
    existing selection. The linked projects' BOMs drive the usage counts."""
    report = db.query(MonthlyReport).filter(MonthlyReport.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    _report_school_guard(db, current_user, report)

    project_ids = body.get("project_ids") or []
    if not isinstance(project_ids, list):
        raise HTTPException(400, "project_ids must be a list")
    project_ids = [int(x) for x in project_ids]

    valid = {p.id for p in db.query(Project.id).filter(
        Project.id.in_(project_ids or [-1]), Project.is_active == True).all()}
    invalid = set(project_ids) - valid
    if invalid:
        raise HTTPException(400, f"Unknown or inactive projects: {sorted(invalid)}")

    db.query(ReportProjectUsage).filter(
        ReportProjectUsage.report_id == report_id).delete()
    for pid in valid:
        db.add(ReportProjectUsage(
            report_id=report_id, project_id=pid, school_id=report.school_id))
    db.commit()
    return {"report_id": report_id, "project_ids": sorted(valid),
            "count": len(valid)}


@router.get("/reports/{report_id}/projects")
def get_report_projects(
    report_id: int,
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    report = db.query(MonthlyReport).filter(MonthlyReport.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    _report_school_guard(db, current_user, report)
    links = (db.query(ReportProjectUsage)
             .filter(ReportProjectUsage.report_id == report_id).all())
    pids = [l.project_id for l in links]
    projs = db.query(Project).filter(Project.id.in_(pids or [-1])).all()
    return {"report_id": report_id, "project_ids": pids,
            "projects": [_project_dict(p) for p in projs]}


# ═══════════════════════════════════════════════════════════════════════════
#  REPORT USED ITEMS & BROKEN ITEMS  (ATL trainer records per monthly report)
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/reports/{report_id}/used-items")
def set_report_used_items(
    report_id: int, body: dict = Body(...),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """ATL trainer records items used this month. Replaces all existing entries."""
    report = db.query(MonthlyReport).filter(MonthlyReport.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    _report_school_guard(db, current_user, report)

    items = body.get("items") or []
    try:
        db.query(ReportUsedItem).filter(ReportUsedItem.report_id == report_id).delete()
    except Exception:
        from app.database import engine, Base
        Base.metadata.create_all(bind=engine)
        db.rollback()
    count = 0
    for it in items:
        name = (it.get("item_name") or "").strip()
        if not name:
            continue
        try:
            qty = max(1, int(it.get("quantity") or 1))
        except (TypeError, ValueError):
            qty = 1
        try:
            ucnt = max(1, int(it.get("usage_count") or 1))
        except (TypeError, ValueError):
            ucnt = 1
        db.add(ReportUsedItem(
            report_id=report_id, school_id=report.school_id,
            item_name=name, quantity=qty, usage_count=ucnt,
        ))
        count += 1
    db.commit()
    return {"report_id": report_id, "count": count}


@router.get("/reports/{report_id}/used-items")
def get_report_used_items(
    report_id: int,
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    report = db.query(MonthlyReport).filter(MonthlyReport.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    _report_school_guard(db, current_user, report)
    rows = (db.query(ReportUsedItem)
            .filter(ReportUsedItem.report_id == report_id)
            .order_by(ReportUsedItem.id).all())
    return [{"id": r.id, "item_name": r.item_name,
             "quantity": r.quantity, "usage_count": r.usage_count or 1} for r in rows]


@router.post("/reports/{report_id}/broken-items")
def set_report_broken_items(
    report_id: int, body: dict = Body(...),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """ATL trainer records items broken/damaged this month. Replaces all existing."""
    report = db.query(MonthlyReport).filter(MonthlyReport.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    _report_school_guard(db, current_user, report)

    items = body.get("items") or []
    try:
        db.query(ReportBrokenItem).filter(ReportBrokenItem.report_id == report_id).delete()
    except Exception:
        from app.database import engine, Base
        Base.metadata.create_all(bind=engine)
        db.rollback()
    count = 0
    for it in items:
        name = (it.get("item_name") or "").strip()
        if not name:
            continue
        try:
            qty = max(1, int(it.get("quantity") or 1))
        except (TypeError, ValueError):
            qty = 1
        db.add(ReportBrokenItem(
            report_id=report_id, school_id=report.school_id,
            item_name=name, quantity=qty,
            reason=(it.get("reason") or "").strip() or None,
        ))
        count += 1
    db.commit()
    return {"report_id": report_id, "count": count}


@router.get("/reports/{report_id}/broken-items")
def get_report_broken_items(
    report_id: int,
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    report = db.query(MonthlyReport).filter(MonthlyReport.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    _report_school_guard(db, current_user, report)
    rows = (db.query(ReportBrokenItem)
            .filter(ReportBrokenItem.report_id == report_id)
            .order_by(ReportBrokenItem.id).all())
    return [{"id": r.id, "item_name": r.item_name,
             "quantity": r.quantity, "reason": r.reason} for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
#  ITEM STATS  (admin "Item Usage Count" tab — KPIs + per-item aggregation)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/item-stats")
def item_stats(
    academic_year: Optional[str] = Query(None),
    month_from: Optional[int] = Query(None),
    month_to: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    school_id: Optional[int] = Query(None),
    district: Optional[str] = Query(None),
    division_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),   # 'working' | 'broken'
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """Aggregated item usage + broken counts + KPI cards for the admin dashboard.

    KPI cards and the report-count badge always reflect the full period+location
    scope so they never zero out when a project / status filter is applied.
    Only the items table is narrowed by project_id / status.
    """
    from collections import defaultdict

    # ── Base scope: period + location filters only ────────────────────────────
    rq = db.query(MonthlyReport).join(School, School.id == MonthlyReport.school_id)

    if not _can_review(current_user):
        ids = _trainer_school_ids(db, current_user)
        rq = rq.filter(MonthlyReport.school_id.in_(ids or [-1]))
    if school_id:
        rq = rq.filter(MonthlyReport.school_id == school_id)
    if district:
        rq = rq.filter(School.district == district)
    if division_id:
        rq = rq.filter(School.division_id == division_id)
    if academic_year:
        rq = rq.filter(MonthlyReport.academic_year == academic_year)
    if year:
        rq = rq.filter(MonthlyReport.report_year == year)
    if month_from:
        rq = rq.filter(MonthlyReport.report_month >= month_from)
    if month_to:
        rq = rq.filter(MonthlyReport.report_month <= month_to)

    all_reports = rq.all()
    all_report_ids = [r.id for r in all_reports]

    # KPIs — latest report per school (running YTD totals, not monthly increments)
    latest_by_school: dict = {}
    for r in all_reports:
        ym = r.report_year * 100 + r.report_month
        prev = latest_by_school.get(r.school_id)
        if prev is None or ym > prev[0]:
            latest_by_school[r.school_id] = (ym, r)
    latest = [v[1] for v in latest_by_school.values()]

    kpis = {
        "total_students":       sum((r.students_school or 0) + (r.students_community or 0) for r in latest),
        "total_workshops":      sum((r.workshops_school or 0) + (r.workshops_community or 0) for r in latest),
        "mentoring_sessions":   sum((r.mentoring_school or 0) + (r.mentoring_community or 0) for r in latest),
        "innovations_projects": sum((r.innovation_school or 0) + (r.innovation_community or 0) for r in latest),
        "experiments":          (db.query(func.count(func.distinct(ReportProjectUsage.project_id)))
                                   .filter(ReportProjectUsage.report_id.in_(all_report_ids or [-1]))
                                   .scalar() or 0),
        "competitions":         sum((r.atl_competitions_participated or 0) + (r.other_competitions_participated or 0) for r in latest),
    }

    # ── Items scope: additionally narrow by project_id for the items table ─────
    item_report_ids = all_report_ids
    if project_id:
        linked = {r.report_id for r in db.query(ReportProjectUsage.report_id).filter(
            ReportProjectUsage.project_id == project_id).all()}
        # Keep only reports that are both in base scope AND used this project
        item_report_ids = [rid for rid in all_report_ids if rid in linked]

    # ── Per-item global aggregation + per-school aggregation (single DB pass) ──
    agg: dict = defaultdict(lambda: {"used_qty": 0, "usage_count": 0, "broken_qty": 0, "report_set": set()})
    # school_id → item_name → {quantity, usage_count}
    sch_used:   dict = defaultdict(lambda: defaultdict(lambda: {"quantity": 0, "usage_count": 0}))
    # school_id → item_name → {quantity, reasons:[]}
    sch_broken: dict = defaultdict(lambda: defaultdict(lambda: {"quantity": 0, "reasons": []}))

    try:
        if status != "broken":
            for row in db.query(ReportUsedItem).filter(
                    ReportUsedItem.report_id.in_(item_report_ids or [-1])).all():
                key = row.item_name.strip()
                agg[key]["used_qty"]    += row.quantity or 1
                agg[key]["usage_count"] += row.usage_count or 1
                agg[key]["report_set"].add(row.report_id)
                if row.school_id:
                    sch_used[row.school_id][key]["quantity"]    += row.quantity or 1
                    sch_used[row.school_id][key]["usage_count"] += row.usage_count or 1
        if status != "working":
            for row in db.query(ReportBrokenItem).filter(
                    ReportBrokenItem.report_id.in_(item_report_ids or [-1])).all():
                key = row.item_name.strip()
                agg[key]["broken_qty"] += row.quantity or 1
                agg[key]["report_set"].add(row.report_id)
                if row.school_id:
                    sch_broken[row.school_id][key]["quantity"] += row.quantity or 1
                    if row.reason and row.reason not in sch_broken[row.school_id][key]["reasons"]:
                        sch_broken[row.school_id][key]["reasons"].append(row.reason)
    except Exception:
        from app.database import engine, Base
        Base.metadata.create_all(bind=engine)
        agg.clear(); sch_used.clear(); sch_broken.clear()

    items_out = []
    for name, d in agg.items():
        if status == "working" and d["used_qty"] == 0:
            continue
        if status == "broken" and d["broken_qty"] == 0:
            continue
        items_out.append({
            "item_name":    name,
            "used_qty":     d["used_qty"],
            "usage_count":  d["usage_count"],
            "broken_qty":   d["broken_qty"],
            "report_count": len(d["report_set"]),
        })
    items_out.sort(key=lambda x: -(x["used_qty"] + x["broken_qty"]))

    # ── Per-school breakdown ──────────────────────────────────────────────────
    all_sids = set(sch_used.keys()) | set(sch_broken.keys())
    sch_objs = {s.id: s for s in db.query(School).filter(
        School.id.in_(all_sids or [-1])).all()} if all_sids else {}

    schools_data = []
    for sid in sorted(all_sids, key=lambda x: sch_objs.get(x, type("_", (), {"name": "~"})()).name):
        sch = sch_objs.get(sid)
        if not sch:
            continue
        all_keys = set(sch_used[sid].keys()) | set(sch_broken[sid].keys())
        rows = []
        for k in sorted(all_keys):
            u = sch_used[sid].get(k, {})
            b = sch_broken[sid].get(k, {})
            used_qty    = u.get("quantity", 0)
            usage_count = u.get("usage_count", 0)
            broken_qty  = b.get("quantity", 0)
            reason      = " | ".join(b.get("reasons", [])) or None
            if status == "working" and used_qty == 0:
                continue
            if status == "broken" and broken_qty == 0:
                continue
            rows.append({
                "item_name":   k,
                "used_qty":    used_qty,
                "usage_count": usage_count,
                "broken_qty":  broken_qty,
                "reason":      reason,
            })
        if rows:
            schools_data.append({
                "school_id":    sid,
                "school_name":  sch.name,
                "district":     sch.district,
                "division_name": sch.division.name if sch.division else None,
                "items": rows,
            })

    # Schools list for the chips row (full base scope)
    school_id_set = {r.school_id for r in all_reports}
    schools = []
    if school_id_set:
        srows = db.query(School).filter(School.id.in_(school_id_set)).order_by(School.name).all()
        schools = [{"id": s.id, "name": s.name, "district": s.district,
                    "division_id": s.division_id,
                    "division_name": s.division.name if s.division else None} for s in srows]

    return {
        "kpis": kpis,
        "items": items_out,
        "schools_data": schools_data,
        "total_reports": len(all_reports),
        "schools": schools,
    }


# ─── EQUIPMENT INSPECTIONS ───────────────────────────────────────────────────

def _serialise_insp_item(it: InspectionItem) -> dict:
    return {
        "id":                  it.id,
        "inspection_id":       it.inspection_id,
        "item_name":           it.item_name,
        "stock_in_register":   it.stock_in_register,
        "currently_available": it.currently_available,
        "working":             it.working,
        "not_working":         it.not_working,
        "missing":             it.missing,
    }


def _serialise_inspection(ins: EquipmentInspection, db: Session = None) -> dict:
    items_out = [_serialise_insp_item(it) for it in ins.items]
    # Enrich each item with the GTTC-issued quantity from equipment_inventory
    if db is not None and ins.school_id:
        issued_map: dict[str, int] = {}
        inv_rows = db.query(EquipmentInventory).filter(
            EquipmentInventory.school_id == ins.school_id
        ).all()
        for row in inv_rows:
            key = row.item_name.strip().lower()
            issued_map[key] = (issued_map.get(key) or 0) + (row.quantity or 0)
        for it in items_out:
            it["supplied_by_gttc"] = issued_map.get(it["item_name"].strip().lower(), 0)
            it["updated_stock"]    = it["currently_available"]
    return {
        "id":              ins.id,
        "school_id":       ins.school_id,
        "school_name":     ins.school.name     if ins.school    else None,
        "district":        ins.school.district if ins.school    else None,
        "inspection_date": ins.inspection_date.isoformat() if ins.inspection_date else None,
        "notes":           ins.notes,
        "submitted_by":    ins.submitted_by,
        "submitter_name":  ins.submitter.name  if ins.submitter else None,
        "created_at":      ins.created_at,
        "items":           items_out,
        "item_count":      len(items_out),
    }


@router.post("/inspections")
def submit_inspection(
    body: dict = Body(...),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """ATL trainer submits a first-time or follow-up equipment inspection."""
    if current_user.role not in (RoleEnum.atl_trainer, RoleEnum.principal):
        raise HTTPException(403, "Only ATL trainers and principals can submit inspections")

    school_id = body.get("school_id")
    if not school_id:
        raise HTTPException(400, "school_id is required")
    allowed = _trainer_school_ids(db, current_user)
    if school_id not in allowed:
        raise HTTPException(403, "You can only inspect your assigned school(s)")

    date_str = (body.get("inspection_date") or "").strip()
    if not date_str:
        raise HTTPException(400, "inspection_date is required")
    try:
        from datetime import date as _date
        inspection_date = _date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(400, "Invalid inspection_date (use YYYY-MM-DD)")

    notes      = (body.get("notes") or "").strip() or None
    items_data = body.get("items") or []
    if not items_data:
        raise HTTPException(400, "At least one equipment item is required")

    ins = EquipmentInspection(
        school_id=school_id,
        inspection_date=inspection_date,
        notes=notes,
        submitted_by=current_user.id,
    )
    db.add(ins)
    db.flush()

    for it in items_data:
        item_name = (it.get("item_name") or "").strip()
        if not item_name:
            continue
        stock_in_register   = max(0, int(it.get("stock_in_register")   or 0))
        currently_available = max(0, int(it.get("currently_available") or 0))
        working             = max(0, int(it.get("working")             or 0))
        not_working         = max(0, int(it.get("not_working")         or 0))
        missing             = max(0, stock_in_register - currently_available)
        db.add(InspectionItem(
            inspection_id=ins.id,
            item_name=item_name,
            stock_in_register=stock_in_register,
            currently_available=currently_available,
            working=working,
            not_working=not_working,
            missing=missing,
        ))

    db.add(ActivityLog(
        user_id=current_user.id, action="Submitted equipment inspection",
        model_type="EquipmentInspection", model_id=ins.id,
        description=f"School #{school_id}, date {inspection_date}, {len(items_data)} items",
    ))
    db.commit()
    db.refresh(ins)
    return _serialise_inspection(ins, db)


@router.get("/inspections")
def list_inspections(
    school_id: Optional[int] = Query(None),
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    """Admin / Division Master sees all; trainers see their own school's inspections."""
    query = db.query(EquipmentInspection)
    if not _can_review(current_user):
        ids = _trainer_school_ids(db, current_user)
        if not ids:
            return []
        query = query.filter(EquipmentInspection.school_id.in_(ids))
    elif school_id:
        query = query.filter(EquipmentInspection.school_id == school_id)

    rows = query.order_by(EquipmentInspection.created_at.desc()).limit(300).all()
    return [_serialise_inspection(ins, db) for ins in rows]


@router.get("/inspections/{inspection_id}")
def get_inspection(
    inspection_id: int,
    db: Session = Depends(get_db), current_user=Depends(require_any),
):
    ins = db.query(EquipmentInspection).filter(EquipmentInspection.id == inspection_id).first()
    if not ins:
        raise HTTPException(404, "Inspection not found")
    if not _can_review(current_user):
        ids = _trainer_school_ids(db, current_user)
        if ins.school_id not in ids:
            raise HTTPException(403, "Access denied")
    return _serialise_inspection(ins, db)
