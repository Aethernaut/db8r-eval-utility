"""EU-8 — Auth dependencies and utilities.

Cookie-session auth with httpOnly cookies, CSRF protection, and role enforcement.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select

from ..config import Settings, get_settings
from ..database import session_scope
from ..models import SessionModel, UserModel

ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password using argon2."""
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a hash."""
    try:
        ph.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False


def generate_token(length: int = 32) -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(length)


def get_current_user_optional(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserModel | None:
    """Get current user from session cookie if present, or None."""
    session_token = request.cookies.get(settings.session_cookie_name)
    if not session_token:
        return None

    with session_scope() as session:
        now = datetime.now(timezone.utc)

        # Look up session
        stmt = select(SessionModel).where(
            SessionModel.token == session_token,
            SessionModel.expires_at > now,
        )
        session_record = session.execute(stmt).scalar_one_or_none()
        if not session_record:
            return None

        # Look up user
        user = session.execute(
            select(UserModel).where(UserModel.id == session_record.user_id)
        ).scalar_one_or_none()

        if user is None or user.disabled:
            return None

        # Refresh session expiry on access (sliding window)
        session_record.expires_at = now + timedelta(hours=settings.session_ttl_hours)

        # Detach user from session so it can be used outside
        session.expunge(user)
        return user


def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserModel:
    """Get current user from session cookie. Raises 401 if not authenticated."""
    user = get_current_user_optional(request, settings)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(
    current_user: Annotated[UserModel, Depends(get_current_user)],
) -> UserModel:
    """Require admin role. Raises 403 if not admin."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def validate_csrf(
    request: Request,
    x_csrf_token: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> None:
    """Validate CSRF token on state-changing requests.

    Uses SameSite=Strict + same-origin as baseline.
    Additionally validates synchronizer token from X-CSRF-Token header.
    """
    # For GET/HEAD/OPTIONS, no CSRF check needed
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    session_token = request.cookies.get(settings.session_cookie_name)
    if not session_token:
        # No session = no CSRF to validate (will fail auth anyway)
        return

    if not x_csrf_token:
        raise HTTPException(status_code=403, detail="CSRF token required")

    # Look up session and validate CSRF token
    with session_scope() as session:
        stmt = select(SessionModel).where(SessionModel.token == session_token)
        session_record = session.execute(stmt).scalar_one_or_none()

        if session_record is None:
            raise HTTPException(status_code=403, detail="Invalid session")

        if not secrets.compare_digest(session_record.csrf_token, x_csrf_token):
            raise HTTPException(status_code=403, detail="Invalid CSRF token")


def create_session(user_id: str, settings: Settings) -> tuple[str, str]:
    """Create a new session for a user.

    Returns (session_token, csrf_token).
    """
    session_token = generate_token()
    csrf_token = generate_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)

    with session_scope() as session:
        session_record = SessionModel(
            token=session_token,
            user_id=user_id,
            csrf_token=csrf_token,
            expires_at=expires_at,
        )
        session.add(session_record)

    return session_token, csrf_token


def delete_session(session_token: str) -> bool:
    """Delete a session. Returns True if deleted."""
    with session_scope() as session:
        stmt = select(SessionModel).where(SessionModel.token == session_token)
        session_record = session.execute(stmt).scalar_one_or_none()
        if session_record:
            session.delete(session_record)
            return True
    return False


def cleanup_expired_sessions() -> int:
    """Delete expired sessions. Returns count deleted."""
    with session_scope() as session:
        now = datetime.now(timezone.utc)
        stmt = select(SessionModel).where(SessionModel.expires_at < now)
        expired = session.execute(stmt).scalars().all()
        count = len(expired)
        for s in expired:
            session.delete(s)
    return count
