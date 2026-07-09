"""Shared pytest fixtures for the project's test suite.

Provides a test database session, a test client, and pre-built test data
(registered user, auth headers) used across multiple test modules.
"""

import os
import uuid

# Must be set before any app imports — SECRET_KEY and DATABASE_URL have no
# test-friendly defaults.
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models import Base
from app.db.session import SoftDeleteSession, get_db
from app.main import app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test.db")

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(
    class_=SoftDeleteSession,
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def override_get_db():
    """Override the production ``get_db`` to return a test session.

    Rolls back after each test to keep the test database clean.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them afterward."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provide a raw SQLAlchemy session for test assertions.

    Tables are already created by the autouse ``setup_database`` fixture.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    """Return a TestClient bound to the FastAPI app with overridden deps."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def registered_user_data():
    """Return a dict of valid registration data (not yet created)."""
    return {
        "email": "test@example.com",
        "password": "securepassword123",
        "full_name": "Test User",
    }


@pytest.fixture
def registered_user(client, registered_user_data):
    """Register a user and return the registration response body."""
    response = client.post(
        f"{settings.API_V1_STR}/auth/register",
        json=registered_user_data,
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def logged_in_user(client, registered_user_data):
    """Register, then log in, and return the login response body."""
    client.post(
        f"{settings.API_V1_STR}/auth/register",
        json=registered_user_data,
    )
    response = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={
            "email": registered_user_data["email"],
            "password": registered_user_data["password"],
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def auth_headers(logged_in_user):
    """Return Authorization headers for the logged-in user."""
    access_token = logged_in_user["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def second_user_data():
    """Return a dict for a second unique user."""
    return {
        "email": f"user-{uuid.uuid4().hex[:8]}@example.com",
        "password": "password456",
        "full_name": "Second User",
    }
