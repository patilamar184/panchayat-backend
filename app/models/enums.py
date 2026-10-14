import enum

import sqlalchemy as sa


class UserRole(str, enum.Enum):
    citizen = "citizen"
    employee = "employee"
    admin = "admin"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ComplaintCategory(str, enum.Enum):
    roads = "roads"
    water = "water"
    electricity = "electricity"
    sanitation = "sanitation"
    streetlight = "streetlight"
    drainage = "drainage"
    garbage = "garbage"
    other = "other"


class ComplaintStatus(str, enum.Enum):
    reported = "reported"
    under_review = "under_review"
    assigned = "assigned"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class NotificationType(str, enum.Enum):
    employee_approved = "employee_approved"
    employee_rejected = "employee_rejected"
    complaint_assigned = "complaint_assigned"
    status_changed = "status_changed"
    complaint_resolved = "complaint_resolved"
    complaint_closed = "complaint_closed"


def db_enum(enum_cls: type[enum.Enum], name: str) -> sa.Enum:
    """Store the lowercase enum *values* in a native PostgreSQL enum type."""
    return sa.Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])
