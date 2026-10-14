from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_id: int | None
    type: NotificationType
    title: str
    message: str
    is_read: bool
    created_at: datetime


class UnreadCount(BaseModel):
    unread: int
