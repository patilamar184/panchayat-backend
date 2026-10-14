from fastapi import APIRouter, Query, status

from app.api.deps import CitizenUser, CurrentUser, DbSession
from app.schemas.common import Page
from app.schemas.complaint import ComplaintCreate, ComplaintRead, HistoryRead
from app.services import complaints as svc

router = APIRouter(prefix="/complaints", tags=["complaints"])


@router.post("", response_model=ComplaintRead, status_code=status.HTTP_201_CREATED)
def create_complaint(data: ComplaintCreate, citizen: CitizenUser, db: DbSession):
    return svc.create_complaint(db, citizen, data)


@router.get("", response_model=Page[ComplaintRead])
def list_my_complaints(
    citizen: CitizenUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = svc.list_complaints(db, page=page, page_size=page_size, citizen_id=citizen.id)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/{complaint_id}", response_model=ComplaintRead)
def get_complaint(complaint_id: int, user: CurrentUser, db: DbSession):
    return svc.get_accessible(db, user, complaint_id)


@router.get("/{complaint_id}/history", response_model=list[HistoryRead])
def get_history(complaint_id: int, user: CurrentUser, db: DbSession):
    complaint = svc.get_accessible(db, user, complaint_id)
    return svc.history_for(db, complaint)
