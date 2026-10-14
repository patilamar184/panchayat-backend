from datetime import date, datetime, time, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import (
    ApprovalStatus,
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
    ComplaintStatusHistory,
    NotificationType,
    User,
    UserRole,
)
from app.schemas.complaint import ComplaintCreate
from app.services import notifications

S = ComplaintStatus

# Which status changes each role may make through the status endpoints.
# Assignment is a separate admin action (see assign_complaint).
ADMIN_TRANSITIONS: dict[S, set[S]] = {
    S.reported: {S.under_review},
    S.under_review: {S.closed},
    S.resolved: {S.closed},
}
EMPLOYEE_TRANSITIONS: dict[S, set[S]] = {
    S.assigned: {S.in_progress},
    S.in_progress: {S.resolved},
    S.resolved: {S.in_progress},
}
ASSIGNABLE_FROM = {S.reported, S.under_review, S.assigned}


def _record(
    db: Session,
    complaint: Complaint,
    actor: User | None,
    action: str,
    previous: S | None,
    new: S,
    notes: str | None,
) -> None:
    db.add(
        ComplaintStatusHistory(
            complaint_id=complaint.id,
            actor_id=actor.id if actor else None,
            action=action,
            previous_status=previous,
            new_status=new,
            notes=notes,
        )
    )


def create_complaint(db: Session, citizen: User, data: ComplaintCreate) -> Complaint:
    complaint = Complaint(citizen_id=citizen.id, status=S.reported, **data.model_dump())
    db.add(complaint)
    db.flush()
    _record(db, complaint, citizen, "created", None, S.reported, None)
    db.commit()
    db.refresh(complaint)
    return complaint


def get_accessible(db: Session, user: User, complaint_id: int) -> Complaint:
    """Return the complaint if this user may see it; otherwise 404 (no existence leak)."""
    complaint = db.get(Complaint, complaint_id)
    allowed = complaint is not None and (
        user.role == UserRole.admin
        or (user.role == UserRole.citizen and complaint.citizen_id == user.id)
        or (
            user.role == UserRole.employee
            and user.approval_status == ApprovalStatus.approved
            and complaint.assigned_employee_id == user.id
        )
    )
    if not allowed:
        raise DomainError(404, "Complaint not found")
    return complaint  # type: ignore[return-value]


def get_owned(db: Session, citizen: User, complaint_id: int) -> Complaint:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None or complaint.citizen_id != citizen.id:
        raise DomainError(404, "Complaint not found")
    return complaint


def history_for(db: Session, complaint: Complaint) -> list[ComplaintStatusHistory]:
    return list(
        db.scalars(
            select(ComplaintStatusHistory)
            .where(ComplaintStatusHistory.complaint_id == complaint.id)
            .order_by(ComplaintStatusHistory.created_at, ComplaintStatusHistory.id)
        )
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_complaints(
    db: Session,
    *,
    page: int,
    page_size: int,
    citizen_id: int | None = None,
    assigned_employee_id: int | None = None,
    status: S | None = None,
    category: ComplaintCategory | None = None,
    unassigned: bool | None = None,
    q: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
) -> tuple[list[Complaint], int]:
    stmt: Select[tuple[Complaint]] = select(Complaint)
    if citizen_id is not None:
        stmt = stmt.where(Complaint.citizen_id == citizen_id)
    if assigned_employee_id is not None:
        stmt = stmt.where(Complaint.assigned_employee_id == assigned_employee_id)
    if status is not None:
        stmt = stmt.where(Complaint.status == status)
    if category is not None:
        stmt = stmt.where(Complaint.category == category)
    if unassigned is True:
        stmt = stmt.where(Complaint.assigned_employee_id.is_(None))
    elif unassigned is False:
        stmt = stmt.where(Complaint.assigned_employee_id.is_not(None))
    if q:
        stmt = stmt.where(Complaint.title.ilike(f"%{_escape_like(q)}%", escape="\\"))
    if created_from:
        stmt = stmt.where(
            Complaint.created_at >= datetime.combine(created_from, time.min, tzinfo=timezone.utc)
        )
    if created_to:
        stmt = stmt.where(
            Complaint.created_at <= datetime.combine(created_to, time.max, tzinfo=timezone.utc)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Complaint.created_at.desc(), Complaint.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def assign_complaint(
    db: Session, admin: User, complaint_id: int, employee_id: int, notes: str | None
) -> Complaint:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise DomainError(404, "Complaint not found")
    employee = db.get(User, employee_id)
    if (
        employee is None
        or employee.role != UserRole.employee
        or employee.approval_status != ApprovalStatus.approved
        or not employee.is_active
    ):
        raise DomainError(400, "Complaints can only be assigned to approved, active employees")
    if complaint.status not in ASSIGNABLE_FROM:
        raise DomainError(409, f"A complaint that is {complaint.status.value} cannot be assigned")

    previous = complaint.status
    reassigned = complaint.assigned_employee_id is not None
    complaint.assigned_employee_id = employee.id
    complaint.status = S.assigned
    _record(db, complaint, admin, "reassigned" if reassigned else "assigned", previous, S.assigned, notes)

    notifications.notify(
        db,
        user_id=employee.id,
        type_=NotificationType.complaint_assigned,
        title="New complaint assigned",
        message=f'Complaint #{complaint.id} "{complaint.title}" has been assigned to you.',
        complaint_id=complaint.id,
    )
    notifications.notify(
        db,
        user_id=complaint.citizen_id,
        type_=NotificationType.complaint_assigned,
        title="Your complaint was assigned",
        message=f'Complaint #{complaint.id} "{complaint.title}" has been assigned to a staff member.',
        complaint_id=complaint.id,
    )
    db.commit()
    db.refresh(complaint)
    return complaint


def change_status(
    db: Session, actor: User, complaint: Complaint, new: S, notes: str | None
) -> Complaint:
    """Apply a status change made by an admin or the assigned employee."""
    table = ADMIN_TRANSITIONS if actor.role == UserRole.admin else EMPLOYEE_TRANSITIONS
    allowed = table.get(complaint.status, set())
    if new not in allowed:
        options = ", ".join(sorted(s.value for s in allowed)) or "none"
        raise DomainError(
            409,
            f"Cannot change status from {complaint.status.value} to {new.value}. "
            f"Allowed for you: {options}",
        )
    notes = notes.strip() if notes else None
    previous = complaint.status
    now = datetime.now(timezone.utc)

    if new == S.resolved:
        if not notes:
            raise DomainError(422, "Resolution notes are required when resolving a complaint")
        complaint.resolution_notes = notes
        complaint.resolved_at = now
        action, ntype = "resolved", NotificationType.complaint_resolved
        title = "Your complaint was resolved"
    elif new == S.closed:
        if previous != S.resolved and not notes:
            raise DomainError(422, "Notes are required when closing a complaint that is not resolved")
        complaint.closed_at = now
        action, ntype = "closed", NotificationType.complaint_closed
        title = "Your complaint was closed"
    elif previous == S.resolved and new == S.in_progress:
        complaint.resolved_at = None
        action, ntype = "reopened", NotificationType.status_changed
        title = "Your complaint was reopened"
    else:
        action, ntype = "status_changed", NotificationType.status_changed
        title = "Complaint status updated"

    complaint.status = new
    _record(db, complaint, actor, action, previous, new, notes)
    notifications.notify(
        db,
        user_id=complaint.citizen_id,
        type_=ntype,
        title=title,
        message=f'Complaint #{complaint.id} "{complaint.title}" is now {new.value.replace("_", " ")}.',
        complaint_id=complaint.id,
    )
    db.commit()
    db.refresh(complaint)
    return complaint
