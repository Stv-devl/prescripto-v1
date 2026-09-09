"""Auth API endpoints — signup, login, refresh, me."""

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, auth_rate_limit, reset_rate_limit
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ProfileUpdateRequest,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UserRead,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=201,
    dependencies=[Depends(auth_rate_limit("signup"))],
)
async def signup(body: SignupRequest, db: DbSession) -> TokenResponse:
    """Register a new user and tenant."""
    _user, access_token, refresh_token = await auth_service.signup(
        db, email=body.email, password=body.password, name=body.name
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(auth_rate_limit("login"))],
)
async def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    """Authenticate and return tokens."""
    _user, access_token, refresh_token = await auth_service.login(
        db, email=body.email, password=body.password
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: DbSession) -> TokenResponse:
    """Refresh an expired access token."""
    access_token, refresh_token = await auth_service.refresh(db, body.refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserRead)
async def me(db: DbSession, user: CurrentUser) -> UserRead:
    """Get the current authenticated user with tenant info."""
    db_user = await auth_service.get_me(db, user["user_id"])
    data = UserRead.model_validate(db_user)
    if db_user.tenant:
        data.tenant_name = db_user.tenant.name
        data.tenant_plan = db_user.tenant.plan
    return data


@router.put("/me", response_model=UserRead)
async def update_me(body: ProfileUpdateRequest, db: DbSession, user: CurrentUser) -> UserRead:
    """Update profile for the authenticated user."""
    db_user = await auth_service.update_profile(
        db, user_id=user["user_id"], first_name=body.first_name, last_name=body.last_name
    )
    data = UserRead.model_validate(db_user)
    if db_user.tenant:
        data.tenant_name = db_user.tenant.name
        data.tenant_plan = db_user.tenant.plan
    return data


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    dependencies=[Depends(reset_rate_limit("forgot-password"))],
)
async def forgot_password(body: ForgotPasswordRequest, db: DbSession) -> MessageResponse:
    """Request a password reset email."""
    await auth_service.forgot_password(db, email=body.email)
    return MessageResponse(message="password reset email sent")


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    dependencies=[Depends(reset_rate_limit("reset-password"))],
)
async def reset_password(body: ResetPasswordRequest, db: DbSession) -> MessageResponse:
    """Reset password using a valid reset token."""
    await auth_service.reset_password(db, token=body.token, new_password=body.password)
    return MessageResponse(message="password reset successful")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest, db: DbSession, user: CurrentUser
) -> MessageResponse:
    """Change password for the authenticated user."""
    await auth_service.change_password(
        db,
        user_id=user["user_id"],
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return MessageResponse(message="password changed successfully")
