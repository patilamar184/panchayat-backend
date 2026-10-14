from fastapi import APIRouter, Query

from app.api.deps import DbSession, EmployeeUser
from app.models import ComplaintStatus
from app.schemas.common import Page
from app.schemas.complaint import ComplaintRead, StatusUpdate
from app.services import complaints as svc

router = APIRouter(prefix="/employee", tags=["employee"])


@router.get("/complaints", response_model=Page[ComplaintRead])
def my_work_queue(
    employee: EmployeeUser,
    db: DbSession,
    status: ComplaintStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = svc.list_complaints(
        db, page=page, page_size=page_size, assigned_employee_id=employee.id, status=status
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/complaints/{complaint_id}/status", response_model=ComplaintRead)
def update_status(complaint_id: int, data: StatusUpdate, employee: EmployeeUser, db: DbSession):
    complaint = svc.get_accessible(db, employee, complaint_id)
    return svc.change_status(db, employee, complaint, data.status, data.notes)
