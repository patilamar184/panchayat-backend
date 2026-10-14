from sqlalchemy import Boolean, Index, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import ApprovalStatus, UserRole, db_enum


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_role_approval_status", "role", "approval_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(db_enum(UserRole, "user_role"), nullable=False)
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        db_enum(ApprovalStatus, "approval_status"),
        nullable=False,
        default=ApprovalStatus.approved,
    )
    department: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
