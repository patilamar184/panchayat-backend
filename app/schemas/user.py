from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import ApprovalStatus, UserRole

Password = Field(min_length=8, max_length=128)


class CitizenRegister(BaseModel):
    email: EmailStr
    password: str = Password
    full_name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=20)


class EmployeeRegister(CitizenRegister):
    department: str = Field(min_length=2, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    phone: str | None
    role: UserRole
    approval_status: ApprovalStatus
    department: str | None
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    department: str | None = Field(default=None, min_length=2, max_length=120)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Password


class DeactivateRequest(BaseModel):
    password: str = Field(max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class OAuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RejectEmployee(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
