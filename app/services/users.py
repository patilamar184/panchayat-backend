from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.security import hash_password, verify_password
from app.models import ApprovalStatus, NotificationType, User, UserRole
from app.services import notifications


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    role: UserRole,
    phone: str | None = None,
    department: str | None = None,
) -> User:
    if get_by_email(db, email):
        raise DomainError(409, "An account with this email already exists")
    user = User(
        email=normalize_email(email),
        hashed_password=hash_password(password),
        full_name=full_name.strip(),
        phone=phone,
        role=role,
        department=department,
        approval_status=(
            ApprovalStatus.pending if role == UserRole.employee else ApprovalStatus.approved
        ),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = get_by_email(db, email)
    if not verify_password(password, user.hashed_password if user else None) or user is None:
        raise DomainError(401, "Invalid email or password")
    if not user.is_active:
        raise DomainError(403, "This account has been deactivated")
    return user


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.hashed_password):
        raise DomainError(400, "Current password is incorrect")
    user.hashed_password = hash_password(new)
    db.commit()


def deactivate(db: Session, user: User, password: str) -> None:
    if user.role == UserRole.admin:
        raise DomainError(403, "Administrator accounts cannot be deactivated here")
    if not verify_password(password, user.hashed_password):
        raise DomainError(400, "Password is incorrect")
    user.is_active = False
    db.commit()


def _get_pending_employee(db: Session, employee_id: int) -> User:
    user = db.get(User, employee_id)
    if user is None or user.role != UserRole.employee:
        raise DomainError(404, "Employee not found")
    if user.approval_status != ApprovalStatus.pending:
        raise DomainError(409, f"Employee registration is already {user.approval_status.value}")
    return user


def approve_employee(db: Session, employee_id: int) -> User:
    user = _get_pending_employee(db, employee_id)
    user.approval_status = ApprovalStatus.approved
    notifications.notify(
        db,
        user_id=user.id,
        type_=NotificationType.employee_approved,
        title="Registration approved",
        message="Your employee account has been approved. You can now receive assignments.",
    )
    db.commit()
    db.refresh(user)
    return user


def reject_employee(db: Session, employee_id: int, reason: str | None) -> User:
    user = _get_pending_employee(db, employee_id)
    user.approval_status = ApprovalStatus.rejected
    message = "Your employee registration was not approved."
    if reason:
        message += f" Reason: {reason}"
    notifications.notify(
        db,
        user_id=user.id,
        type_=NotificationType.employee_rejected,
        title="Registration rejected",
        message=message,
    )
    db.commit()
    db.refresh(user)
    return user
