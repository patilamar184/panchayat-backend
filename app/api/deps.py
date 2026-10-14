from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import ApprovalStatus, User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_access_token(token)
    if user_id is None:
        raise unauthorized
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def _require_role(role: UserRole):
    def checker(user: CurrentUser) -> User:
        if user.role != role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"{role.value.capitalize()} access required")
        return user

    return checker


def require_approved_employee(user: Annotated[User, Depends(_require_role(UserRole.employee))]) -> User:
    if user.approval_status != ApprovalStatus.approved:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Your employee account is not approved by an administrator"
        )
    return user


CitizenUser = Annotated[User, Depends(_require_role(UserRole.citizen))]
AdminUser = Annotated[User, Depends(_require_role(UserRole.admin))]
EmployeeUser = Annotated[User, Depends(require_approved_employee)]
