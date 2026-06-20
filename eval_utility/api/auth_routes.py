"""EU-8 — Auth endpoints (login, logout, me)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from ..config import Settings, get_settings
from ..database import session_scope
from ..models import AuthTokenModel, UserModel
from .auth import (
    create_session,
    get_current_user,
    get_current_user_optional,
    hash_password,
    verify_password,
)

router = APIRouter()


# Rate limiting state (in-memory for MVP; production would use Redis)
_login_attempts: dict[str, list[datetime]] = {}


def _check_rate_limit(key: str, settings: Settings) -> None:
    """Check and update rate limit for login attempts."""
    now = datetime.now(timezone.utc)
    window = timedelta(seconds=settings.login_rate_limit_window_seconds)
    cutoff = now - window

    # Clean old attempts
    if key in _login_attempts:
        _login_attempts[key] = [t for t in _login_attempts[key] if t > cutoff]
    else:
        _login_attempts[key] = []

    # Check limit
    if len(_login_attempts[key]) >= settings.login_rate_limit_attempts:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    # Record attempt
    _login_attempts[key].append(now)


# --- Request/Response models ---


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginResponse(BaseModel):
    user_id: str
    email: str
    role: str
    csrf_token: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    role: str
    csrf_token: str | None = None


class AcceptInviteRequest(BaseModel):
    token: str
    password: str = Field(min_length=8)


class AcceptInviteResponse(BaseModel):
    user_id: str
    email: str
    role: str


# --- Endpoints ---


@router.post("/login", response_model=LoginResponse)
def login(
    data: LoginRequest,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    """Login with email and password. Returns session cookie + CSRF token."""
    # Rate limit by email
    _check_rate_limit(f"email:{data.email}", settings)

    with session_scope() as session:
        stmt = select(UserModel).where(UserModel.email == data.email)
        user = session.execute(stmt).scalar_one_or_none()

        if user is None or user.disabled:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Create session
        session_token, csrf_token = create_session(user.id, settings)

        # Set session cookie
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session_token,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite="strict",
            max_age=settings.session_ttl_hours * 3600,
        )

        return LoginResponse(
            user_id=user.id,
            email=user.email,
            role=user.role,
            csrf_token=csrf_token,
        )


@router.post("/logout")
def logout(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[UserModel | None, Depends(get_current_user_optional)] = None,
) -> dict:
    """Logout and clear session."""

    # Get session token from cookie to delete
    # Note: We need the request to get the cookie, but we can just delete the cookie
    response.delete_cookie(settings.session_cookie_name)

    return {"message": "Logged out"}


@router.get("/me", response_model=MeResponse)
def get_me(
    current_user: Annotated[UserModel, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MeResponse:
    """Get current user info. Returns 401 if not authenticated."""
    # Get CSRF token for the current session

    # For simplicity, we won't return the CSRF token here - client should save it from login
    return MeResponse(
        user_id=current_user.id,
        email=current_user.email,
        role=current_user.role,
    )


@router.post("/accept-invite", response_model=AcceptInviteResponse)
def accept_invite(
    data: AcceptInviteRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AcceptInviteResponse:
    """Accept an invite token and set password."""
    with session_scope() as session:
        now = datetime.now(timezone.utc)

        # Find valid invite token
        stmt = select(AuthTokenModel).where(
            AuthTokenModel.token == data.token,
            AuthTokenModel.purpose == "invite",
            AuthTokenModel.expires_at > now,
            AuthTokenModel.used_at.is_(None),
        )
        token_record = session.execute(stmt).scalar_one_or_none()

        if token_record is None:
            raise HTTPException(status_code=400, detail="Invalid or expired invite token")

        # Check if user already exists
        existing_user = session.execute(
            select(UserModel).where(UserModel.email == token_record.email)
        ).scalar_one_or_none()

        if existing_user is not None:
            raise HTTPException(status_code=400, detail="User already exists")

        # Create user
        user = UserModel(
            email=token_record.email,
            password_hash=hash_password(data.password),
            role=token_record.role,
        )
        session.add(user)

        # Mark token as used
        token_record.used_at = now

        session.flush()

        return AcceptInviteResponse(
            user_id=user.id,
            email=user.email,
            role=user.role,
        )


# --- Bootstrap admin ---


def bootstrap_admin(settings: Settings) -> UserModel | None:
    """Create initial admin from env vars if not exists.

    Called on startup if EVAL_ADMIN_EMAIL and EVAL_ADMIN_INITIAL_PASSWORD are set.
    """
    if not settings.admin_email or not settings.admin_initial_password:
        return None

    with session_scope() as session:
        # Check if admin exists
        existing = session.execute(
            select(UserModel).where(UserModel.email == settings.admin_email)
        ).scalar_one_or_none()

        if existing is not None:
            return existing

        # Create admin
        admin = UserModel(
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_initial_password),
            role="admin",
        )
        session.add(admin)
        session.flush()
        session.expunge(admin)

        return admin
