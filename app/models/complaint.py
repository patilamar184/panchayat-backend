from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin
from app.models.enums import ComplaintCategory, ComplaintStatus, db_enum


class Complaint(TimestampMixin, Base):
    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="latitude_range"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="longitude_range"),
        Index("ix_complaints_citizen_id", "citizen_id"),
        Index("ix_complaints_assigned_employee_id", "assigned_employee_id"),
        Index("ix_complaints_status", "status"),
        Index("ix_complaints_category", "category"),
        Index("ix_complaints_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[ComplaintCategory] = mapped_column(
        db_enum(ComplaintCategory, "complaint_category"), nullable=False
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    status: Mapped[ComplaintStatus] = mapped_column(
        db_enum(ComplaintStatus, "complaint_status"),
        nullable=False,
        default=ComplaintStatus.reported,
    )
    citizen_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assigned_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    history: Mapped[list["ComplaintStatusHistory"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="ComplaintStatusHistory.id",
        passive_deletes=True,
    )
    media: Mapped[list["ComplaintMedia"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="ComplaintMedia.id",
        passive_deletes=True,
    )


class ComplaintStatusHistory(CreatedAtMixin, Base):
    __tablename__ = "complaint_status_history"
    __table_args__ = (Index("ix_complaint_status_history_complaint_id_created_at", "complaint_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[ComplaintStatus | None] = mapped_column(
        db_enum(ComplaintStatus, "complaint_status")
    )
    new_status: Mapped[ComplaintStatus] = mapped_column(
        db_enum(ComplaintStatus, "complaint_status"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)

    complaint: Mapped[Complaint] = relationship(back_populates="history")


class ComplaintMedia(CreatedAtMixin, Base):
    __tablename__ = "complaint_media"
    __table_args__ = (Index("ix_complaint_media_complaint_id", "complaint_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    width: Mapped[int] = mapped_column(nullable=False)
    height: Mapped[int] = mapped_column(nullable=False)

    complaint: Mapped[Complaint] = relationship(back_populates="media")
