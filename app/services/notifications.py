from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import Notification, NotificationType


def notify(
    db: Session,
    *,
    user_id: int,
    type_: NotificationType,
    title: str,
    message: str,
    complaint_id: int | None = None,
) -> Notification:
    """Add a notification to the session. The caller commits."""
    n = Notification(
        user_id=user_id, type=type_, title=title, message=message, complaint_id=complaint_id
    )
    db.add(n)
    return n


def list_for_user(
    db: Session, user_id: int, *, unread_only: bool, page: int, page_size: int
) -> tuple[list[Notification], int]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def unread_count(db: Session, user_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        )
        or 0
    )


def mark_read(db: Session, user_id: int, notification_id: int) -> Notification:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user_id:
        raise DomainError(404, "Notification not found")
    n.is_read = True
    db.commit()
    db.refresh(n)
    return n


def mark_all_read(db: Session, user_id: int) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return result.rowcount or 0
