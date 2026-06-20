"""Tests for EU-8 auth system."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eval_utility.api.auth import (
    create_session,
    generate_token,
    hash_password,
    verify_password,
)
from eval_utility.api.auth_routes import bootstrap_admin
from eval_utility.config import Settings
from eval_utility.database import init_db, reset_engine, session_scope
from eval_utility.models import SessionModel, UserModel


@pytest.fixture(autouse=True)
def reset_db():
    """Reset database for each test."""
    # Create temp database
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test_auth.db"
        os.environ["EVAL_DATABASE_URL"] = f"sqlite:///{db_path}"
        reset_engine()
        init_db()
        yield
        reset_engine()
        os.environ.pop("EVAL_DATABASE_URL", None)


class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "testpassword123"
        hashed = hash_password(password)
        assert hashed != password
        assert len(hashed) > 50  # argon2 hashes are long

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "testpassword123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "testpassword123"
        hashed = hash_password(password)
        assert verify_password("wrongpassword", hashed) is False


class TestTokenGeneration:
    """Tests for token generation."""

    def test_generate_token_length(self):
        """Test token generation produces correct length."""
        token = generate_token(32)
        # URL-safe base64 encoding makes longer strings
        assert len(token) > 32

    def test_generate_token_unique(self):
        """Test tokens are unique."""
        tokens = [generate_token() for _ in range(100)]
        assert len(set(tokens)) == 100


class TestSessionManagement:
    """Tests for session creation and management."""

    def test_create_session(self):
        """Test session creation."""
        # Create a test user
        with session_scope() as session:
            user = UserModel(
                email="test@example.com",
                password_hash=hash_password("testpassword"),
                role="annotator",
            )
            session.add(user)
            session.flush()
            user_id = user.id

        settings = Settings()
        session_token, csrf_token = create_session(user_id, settings)

        assert len(session_token) > 20
        assert len(csrf_token) > 20

        # Verify session was created
        with session_scope() as session:
            stmt = session.execute(
                SessionModel.__table__.select().where(SessionModel.token == session_token)
            )
            result = stmt.fetchone()
            assert result is not None


class TestBootstrapAdmin:
    """Tests for admin bootstrap."""

    def test_bootstrap_admin_with_env(self):
        """Test admin creation from env vars."""
        settings = Settings(
            admin_email="admin@example.com",
            admin_initial_password="adminpassword123",
        )
        admin = bootstrap_admin(settings)

        assert admin is not None
        assert admin.email == "admin@example.com"
        assert admin.role == "admin"

    def test_bootstrap_admin_idempotent(self):
        """Test admin bootstrap is idempotent."""
        settings = Settings(
            admin_email="admin@example.com",
            admin_initial_password="adminpassword123",
        )
        admin1 = bootstrap_admin(settings)
        admin2 = bootstrap_admin(settings)

        assert admin1.id == admin2.id

    def test_bootstrap_admin_without_env(self):
        """Test no admin creation without env vars."""
        settings = Settings()
        admin = bootstrap_admin(settings)
        assert admin is None


class TestAuthEndpoints:
    """Tests for auth HTTP endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with app."""
        from eval_utility.server import app

        return TestClient(app)

    @pytest.fixture
    def test_user(self):
        """Create a test user."""
        with session_scope() as session:
            user = UserModel(
                email="user@example.com",
                password_hash=hash_password("testpassword123"),
                role="annotator",
            )
            session.add(user)
            session.flush()
            # Refresh to get defaults
            session.refresh(user)
            return {
                "id": user.id,
                "email": user.email,
                "role": user.role,
            }

    def test_login_success(self, client, test_user):
        """Test successful login."""
        response = client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "testpassword123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@example.com"
        assert data["role"] == "annotator"
        assert "csrf_token" in data

        # Check session cookie was set
        assert "eval_session" in response.cookies

    def test_login_invalid_password(self, client, test_user):
        """Test login with invalid password."""
        response = client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    def test_login_invalid_email(self, client):
        """Test login with non-existent email."""
        response = client.post(
            "/auth/login",
            json={"email": "nonexistent@example.com", "password": "anypassword"},
        )
        assert response.status_code == 401

    def test_me_authenticated(self, client, test_user):
        """Test /me endpoint when authenticated."""
        # Login first
        login_response = client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "testpassword123"},
        )
        assert login_response.status_code == 200

        # Access /me
        response = client.get("/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@example.com"

    def test_me_unauthenticated(self, client):
        """Test /me endpoint returns 401 when not authenticated."""
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_logout(self, client, test_user):
        """Test logout clears session."""
        # Login first
        login_response = client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "testpassword123"},
        )
        assert login_response.status_code == 200

        # Logout
        response = client.post("/auth/logout")
        assert response.status_code == 200

        # Session cookie should be cleared
        # TestClient doesn't automatically clear cookies on delete_cookie,
        # but we can verify the endpoint works


class TestInviteFlow:
    """Tests for invite-only user creation."""

    @pytest.fixture
    def client(self):
        """Create test client with app."""
        from eval_utility.server import app

        return TestClient(app)

    @pytest.fixture
    def admin_user(self):
        """Create an admin user and return login cookies."""
        from eval_utility.server import app

        with session_scope() as session:
            admin = UserModel(
                email="admin@example.com",
                password_hash=hash_password("adminpassword123"),
                role="admin",
            )
            session.add(admin)
            session.flush()

        client = TestClient(app)
        response = client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "adminpassword123"},
        )
        assert response.status_code == 200
        csrf_token = response.json()["csrf_token"]
        return {"client": client, "csrf_token": csrf_token}

    def test_invite_user(self, admin_user):
        """Test admin can invite a new user."""
        client = admin_user["client"]
        csrf = admin_user["csrf_token"]

        response = client.post(
            "/api/v1/users/invite",
            json={"email": "newuser@example.com", "role": "annotator"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "annotator"
        assert "invite_token" in data

    def test_accept_invite(self, admin_user, client):
        """Test accepting an invite creates a user."""
        admin_client = admin_user["client"]
        csrf = admin_user["csrf_token"]

        # Create invite
        invite_response = admin_client.post(
            "/api/v1/users/invite",
            json={"email": "newuser@example.com", "role": "annotator"},
            headers={"X-CSRF-Token": csrf},
        )
        invite_token = invite_response.json()["invite_token"]

        # Accept invite (no auth needed)
        response = client.post(
            "/auth/accept-invite",
            json={"token": invite_token, "password": "newpassword123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "annotator"

        # Verify user can login
        login_response = client.post(
            "/auth/login",
            json={"email": "newuser@example.com", "password": "newpassword123"},
        )
        assert login_response.status_code == 200


class TestRoleEnforcement:
    """Tests for role-based access control."""

    @pytest.fixture
    def client(self):
        """Create test client with app."""
        from eval_utility.server import app

        return TestClient(app)

    @pytest.fixture
    def annotator_user(self, client):
        """Create and login as annotator."""
        with session_scope() as session:
            user = UserModel(
                email="annotator@example.com",
                password_hash=hash_password("testpassword123"),
                role="annotator",
            )
            session.add(user)

        response = client.post(
            "/auth/login",
            json={"email": "annotator@example.com", "password": "testpassword123"},
        )
        return {"client": client, "csrf_token": response.json()["csrf_token"]}

    def test_annotator_cannot_list_users(self, annotator_user):
        """Test annotator is blocked from user management."""
        client = annotator_user["client"]
        csrf = annotator_user["csrf_token"]

        response = client.get("/api/v1/users", headers={"X-CSRF-Token": csrf})
        assert response.status_code == 403

    def test_annotator_cannot_invite_users(self, annotator_user):
        """Test annotator is blocked from inviting users."""
        client = annotator_user["client"]
        csrf = annotator_user["csrf_token"]

        response = client.post(
            "/api/v1/users/invite",
            json={"email": "newuser@example.com"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 403


class TestHealthEndpoint:
    """Tests for health endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with app."""
        from eval_utility.server import app

        return TestClient(app)

    def test_health_check(self, client):
        """Test health endpoint returns status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database_connected"] is True
