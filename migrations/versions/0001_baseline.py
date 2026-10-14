"""Baseline schema for Panchayat.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

ENUMS = {
    "user_role": ("citizen", "employee", "admin"),
    "approval_status": ("pending", "approved", "rejected"),
    "complaint_category": (
        "roads", "water", "electricity", "sanitation", "streetlight", "drainage", "garbage", "other",
    ),
    "complaint_status": ("reported", "under_review", "assigned", "in_progress", "resolved", "closed"),
    "notification_type": (
        "employee_approved", "employee_rejected", "complaint_assigned",
        "status_changed", "complaint_resolved", "complaint_closed",
    ),
}


def enum(name: str) -> postgresql.ENUM:
    # create_type=False: the types are created explicitly below, once each.
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def upgrade() -> None:
    for name, values in ENUMS.items():
        quoted = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({quoted})")

    now = sa.text("now()")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", enum("user_role"), nullable=False),
        sa.Column("approval_status", enum("approval_status"), nullable=False),
        sa.Column("department", sa.String(120), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index("ix_users_role_approval_status", "users", ["role", "approval_status"])

    op.create_table(
        "complaints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", enum("complaint_category"), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", enum("complaint_status"), nullable=False),
        sa.Column("citizen_id", sa.Integer(), nullable=False),
        sa.Column("assigned_employee_id", sa.Integer(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name=op.f("ck_complaints_latitude_range")),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name=op.f("ck_complaints_longitude_range")),
        sa.ForeignKeyConstraint(
            ["citizen_id"], ["users.id"], name=op.f("fk_complaints_citizen_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assigned_employee_id"],
            ["users.id"],
            name=op.f("fk_complaints_assigned_employee_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_complaints")),
    )
    op.create_index("ix_complaints_citizen_id", "complaints", ["citizen_id"])
    op.create_index("ix_complaints_assigned_employee_id", "complaints", ["assigned_employee_id"])
    op.create_index("ix_complaints_status", "complaints", ["status"])
    op.create_index("ix_complaints_category", "complaints", ["category"])
    op.create_index("ix_complaints_created_at", "complaints", ["created_at"])

    op.create_table(
        "complaint_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("complaint_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("previous_status", enum("complaint_status"), nullable=True),
        sa.Column("new_status", enum("complaint_status"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.ForeignKeyConstraint(
            ["complaint_id"],
            ["complaints.id"],
            name=op.f("fk_complaint_status_history_complaint_id_complaints"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_complaint_status_history_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_complaint_status_history")),
    )
    op.create_index(
        "ix_complaint_status_history_complaint_id_created_at",
        "complaint_status_history",
        ["complaint_id", "created_at"],
    )

    op.create_table(
        "complaint_media",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("complaint_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.ForeignKeyConstraint(
            ["complaint_id"],
            ["complaints.id"],
            name=op.f("fk_complaint_media_complaint_id_complaints"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            name=op.f("fk_complaint_media_uploaded_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_complaint_media")),
        sa.UniqueConstraint("stored_filename", name=op.f("uq_complaint_media_stored_filename")),
    )
    op.create_index("ix_complaint_media_complaint_id", "complaint_media", ["complaint_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("complaint_id", sa.Integer(), nullable=True),
        sa.Column("type", enum("notification_type"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_notifications_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["complaint_id"],
            ["complaints.id"],
            name=op.f("fk_notifications_complaint_id_complaints"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index("ix_notifications_user_id_is_read", "notifications", ["user_id", "is_read"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("complaint_media")
    op.drop_table("complaint_status_history")
    op.drop_table("complaints")
    op.drop_table("users")
    for name in reversed(list(ENUMS)):
        op.execute(f"DROP TYPE {name}")
