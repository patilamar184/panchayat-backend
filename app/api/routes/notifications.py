from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Page
from app.schemas.notification import NotificationRead, UnreadCount
from app.services import notifications as svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationRead])
def list_notifications(
    user: CurrentUser,
    db: DbSession,
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = svc.list_for_user(db, user.id, unread_only=unread_only, page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/unread", response_model=Page[NotificationRead])
def list_unread(
    user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = svc.list_for_user(db, user.id, unread_only=True, page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(user: CurrentUser, db: DbSession):
    return UnreadCount(unread=svc.unread_count(db, user.id))


@router.post("/read-all", response_model=UnreadCount)
def read_all(user: CurrentUser, db: DbSession):
    svc.mark_all_read(db, user.id)
    return UnreadCount(unread=0)


@router.post("/{notification_id}/read", response_model=NotificationRead)
def read_one(notification_id: int, user: CurrentUser, db: DbSession):
    return svc.mark_read(db, user.id, notification_id)
