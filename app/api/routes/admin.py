from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, DbSession
from app.models import ApprovalStatus, ComplaintCategory, ComplaintStatus, User, UserRole
from app.schemas.common import Page
from app.schemas.complaint import AssignRequest, ComplaintRead, StatusUpdate
from app.schemas.user import RejectEmployee, UserRead
from app.services import complaints as svc
from app.services import users as user_svc
from sqlalchemy import func, select

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/employees", response_model=Page[UserRead])
def list_employees(
    _: AdminUser,
    db: DbSession,
    approval_status: ApprovalStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = select(User).where(User.role == UserRole.employee)
    if approval_status:
        stmt = stmt.where(User.approval_status == approval_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page(items=list(items), total=total, page=page, page_size=page_size)


@router.post("/employees/{employee_id}/approve", response_model=UserRead)
def approve_employee(employee_id: int, _: AdminUser, db: DbSession):
    return user_svc.approve_employee(db, employee_id)


@router.post("/employees/{employee_id}/reject", response_model=UserRead)
def reject_employee(employee_id: int, data: RejectEmployee, _: AdminUser, db: DbSession):
    return user_svc.reject_employee(db, employee_id, data.reason)


@router.get("/complaints", response_model=Page[ComplaintRead])
def list_complaints(
    _: AdminUser,
    db: DbSession,
    status: ComplaintStatus | None = None,
    category: ComplaintCategory | None = None,
    citizen_id: int | None = None,
    assigned_employee_id: int | None = None,
    unassigned: bool | None = None,
    q: str | None = Query(None, max_length=100, description="Search in title"),
    created_from: date | None = None,
    created_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = svc.list_complaints(
        db,
        page=page,
        page_size=page_size,
        citizen_id=citizen_id,
        assigned_employee_id=assigned_employee_id,
        status=status,
        category=category,
        unassigned=unassigned,
        q=q,
        created_from=created_from,
        created_to=created_to,
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/complaints/{complaint_id}/assign", response_model=ComplaintRead)
def assign_complaint(complaint_id: int, data: AssignRequest, admin: AdminUser, db: DbSession):
    return svc.assign_complaint(db, admin, complaint_id, data.employee_id, data.notes)


@router.post("/complaints/{complaint_id}/status", response_model=ComplaintRead)
def update_status(complaint_id: int, data: StatusUpdate, admin: AdminUser, db: DbSession):
    complaint = svc.get_accessible(db, admin, complaint_id)
    return svc.change_status(db, admin, complaint, data.status, data.notes)
