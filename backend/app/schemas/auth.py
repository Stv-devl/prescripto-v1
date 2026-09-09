"""Auth schemas — request/response models for authentication endpoints."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

MAX_PASSWORD_BYTES = 72


def _within_bcrypt_limit(value: str) -> str:
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
    return value


NewPassword = Annotated[
    str, Field(min_length=8, max_length=128), AfterValidator(_within_bcrypt_limit)
]
GivenPassword = Annotated[str, AfterValidator(_within_bcrypt_limit)]


class SignupRequest(BaseModel):
    email: EmailStr
    password: NewPassword
    name: str = Field(min_length=1, max_length=255, description="Cabinet name")


class LoginRequest(BaseModel):
    email: EmailStr
    password: GivenPassword


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: NewPassword


class ChangePasswordRequest(BaseModel):
    current_password: GivenPassword
    new_password: NewPassword


class MessageResponse(BaseModel):
    message: str


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    tenant_id: uuid.UUID
    first_name: str | None = None
    last_name: str | None = None
    tenant_name: str | None = None
    tenant_plan: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
