from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ComplaintCategory, ComplaintStatus


class ComplaintCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    category: ComplaintCategory
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str = Field(min_length=3, max_length=500)
    is_public: bool = False


class MediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_id: int
    original_filename: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    created_at: datetime


class ComplaintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category: ComplaintCategory
    latitude: float
    longitude: float
    address: str
    is_public: bool
    status: ComplaintStatus
    citizen_id: int
    assigned_employee_id: int | None
    resolution_notes: str | None
    resolved_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class HistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_id: int
    actor_id: int | None
    action: str
    previous_status: ComplaintStatus | None
    new_status: ComplaintStatus
    notes: str | None
    created_at: datetime


class AssignRequest(BaseModel):
    employee_id: int
    notes: str | None = Field(default=None, max_length=1000)


class StatusUpdate(BaseModel):
    status: ComplaintStatus
    notes: str | None = Field(default=None, max_length=2000)
