from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Message
from app.schemas.user import DeactivateRequest, PasswordChange, UserRead, UserUpdate
from app.services import users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserRead)
def update_me(data: UserUpdate, user: CurrentUser, db: DbSession):
    changes = data.model_dump(exclude_unset=True)
    if "full_name" in changes and changes["full_name"] is None:
        changes.pop("full_name")
    if "department" in changes and user.role.value != "employee":
        changes.pop("department")
    for key, value in changes.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/password", response_model=Message)
def change_password(data: PasswordChange, user: CurrentUser, db: DbSession):
    users.change_password(db, user, data.current_password, data.new_password)
    return Message(detail="Password updated")


@router.post("/me/deactivate", response_model=Message)
def deactivate_me(data: DeactivateRequest, user: CurrentUser, db: DbSession):
    users.deactivate(db, user, data.password)
    return Message(detail="Account deactivated")
