"""EU-8 — User management endpoints (admin-only)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from ..config import Settings, get_settings
from ..database import session_scope
from ..models import AuditLogModel, AuthTokenModel, UserModel
from .auth import generate_token, require_admin

router = APIRouter()


# --- Request/Response models ---


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    disabled: bool
    created_at: str
    updated_at: str


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="annotator", pattern="^(admin|annotator)$")


class InviteUserResponse(BaseModel):
    email: str
    role: str
    invite_token: str
    expires_at: str


class UpdateUserRequest(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|annotator)$")
    disabled: bool | None = None


# --- Endpoints ---


@router.get("", response_model=UserListResponse)
def list_users(
    admin: Annotated[UserModel, Depends(require_admin)],
    offset: int = 0,
    limit: int = 50,
) -> UserListResponse:
    """List all users (admin only)."""
    with session_scope() as session:
        stmt = select(UserModel).order_by(UserModel.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)
        users = session.execute(stmt).scalars().all()

        count = session.execute(select(func.count()).select_from(UserModel)).scalar() or 0

    return UserListResponse(
        users=[
            UserResponse(
                id=u.id,
                email=u.email,
                role=u.role,
                disabled=u.disabled,
                created_at=u.created_at.isoformat() if u.created_at else "",
                updated_at=u.updated_at.isoformat() if u.updated_at else "",
            )
            for u in users
        ],
        total=count,
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    admin: Annotated[UserModel, Depends(require_admin)],
) -> UserResponse:
    """Get a user by ID (admin only)."""
    with session_scope() as session:
        user = session.execute(
            select(UserModel).where(UserModel.id == user_id)
        ).scalar_one_or_none()

        if user is None:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        return UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            disabled=user.disabled,
            created_at=user.created_at.isoformat() if user.created_at else "",
            updated_at=user.updated_at.isoformat() if user.updated_at else "",
        )


@router.post("/invite", response_model=InviteUserResponse)
def invite_user(
    data: InviteUserRequest,
    admin: Annotated[UserModel, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InviteUserResponse:
    """Create an invite for a new user (admin only)."""
    with session_scope() as session:
        # Check if email already exists
        existing = session.execute(
            select(UserModel).where(UserModel.email == data.email)
        ).scalar_one_or_none()

        if existing is not None:
            raise HTTPException(status_code=400, detail="User with this email already exists")

        # Check for existing unused invite
        existing_invite = session.execute(
            select(AuthTokenModel).where(
                AuthTokenModel.email == data.email,
                AuthTokenModel.purpose == "invite",
                AuthTokenModel.used_at.is_(None),
            )
        ).scalar_one_or_none()

        if existing_invite is not None:
            # Revoke old invite
            session.delete(existing_invite)

        # Create invite token
        token = generate_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.invite_token_ttl_hours)

        invite = AuthTokenModel(
            token=token,
            email=data.email,
            role=data.role,
            purpose="invite",
            expires_at=expires_at,
        )
        session.add(invite)

        # Audit log
        audit = AuditLogModel(
            user_id=admin.id,
            action="user_invite",
            target_type="user",
            target_id=data.email,
            details={"role": data.role},
        )
        session.add(audit)

        return InviteUserResponse(
            email=data.email,
            role=data.role,
            invite_token=token,
            expires_at=expires_at.isoformat(),
        )


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    data: UpdateUserRequest,
    admin: Annotated[UserModel, Depends(require_admin)],
) -> UserResponse:
    """Update a user (admin only). Can change role or disable."""
    with session_scope() as session:
        user = session.execute(
            select(UserModel).where(UserModel.id == user_id)
        ).scalar_one_or_none()

        if user is None:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        # Prevent disabling yourself
        if user_id == admin.id and data.disabled is True:
            raise HTTPException(status_code=400, detail="Cannot disable yourself")

        # Apply updates
        changes = {}
        if data.role is not None:
            changes["role"] = {"old": user.role, "new": data.role}
            user.role = data.role
        if data.disabled is not None:
            changes["disabled"] = {"old": user.disabled, "new": data.disabled}
            user.disabled = data.disabled

        # Audit log
        if changes:
            audit = AuditLogModel(
                user_id=admin.id,
                action="user_update",
                target_type="user",
                target_id=user_id,
                details=changes,
            )
            session.add(audit)

        session.flush()

        return UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            disabled=user.disabled,
            created_at=user.created_at.isoformat() if user.created_at else "",
            updated_at=user.updated_at.isoformat() if user.updated_at else "",
        )


@router.delete("/{user_id}", status_code=204)
def disable_user(
    user_id: str,
    admin: Annotated[UserModel, Depends(require_admin)],
) -> Response:
    """Disable a user (admin only). Soft-delete via disabled flag."""
    with session_scope() as session:
        user = session.execute(
            select(UserModel).where(UserModel.id == user_id)
        ).scalar_one_or_none()

        if user is None:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        # Prevent disabling yourself
        if user_id == admin.id:
            raise HTTPException(status_code=400, detail="Cannot disable yourself")

        user.disabled = True

        # Audit log
        audit = AuditLogModel(
            user_id=admin.id,
            action="user_disable",
            target_type="user",
            target_id=user_id,
        )
        session.add(audit)

    return Response(status_code=204)
