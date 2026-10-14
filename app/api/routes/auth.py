from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DbSession
from app.core.security import create_access_token
from app.models import UserRole
from app.schemas.user import (
    CitizenRegister,
    EmployeeRegister,
    LoginRequest,
    OAuthToken,
    TokenResponse,
    UserRead,
)
from app.services import users

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register/citizen", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_citizen(data: CitizenRegister, db: DbSession):
    return users.create_user(
        db,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        phone=data.phone,
        role=UserRole.citizen,
    )


@router.post("/register/employee", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_employee(data: EmployeeRegister, db: DbSession):
    """Creates an employee in *pending* state. An administrator must approve it."""
    return users.create_user(
        db,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        phone=data.phone,
        department=data.department,
        role=UserRole.employee,
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: DbSession):
    user = users.authenticate(db, data.email, data.password)
    return TokenResponse(access_token=create_access_token(user.id, user.role.value), user=user)


@router.post("/token", response_model=OAuthToken, include_in_schema=True)
def token(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    """Form-based login used by the Swagger 'Authorize' button (username = email)."""
    user = users.authenticate(db, form.username, form.password)
    return OAuthToken(access_token=create_access_token(user.id, user.role.value))
