"""Authentication service — register, login, token refresh.

Uses bcrypt for password hashing and python-jose for JWT creation/validation.
Soft-deleted users cannot log in or refresh tokens.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from fastapi import BackgroundTasks
from jose import JWTError, jwt
from pydantic import UUID4

from app.core.config import settings
from app.db.models import User
from app.db.session import Session
from app.exceptions.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserNotFoundError,
)
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.email import send_activation_email


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*.

    Passwords longer than 72 bytes are SHA-256 pre-hashed to avoid
    the ``bcrypt`` built-in length restriction.
    """
    pre = hashlib.sha256(plain.encode()).digest()
    return bcrypt.hashpw(pre, bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` when *plain* matches *hashed*."""
    pre = hashlib.sha256(plain.encode()).digest()
    return bcrypt.checkpw(pre, hashed.encode())


def create_access_token(user_id: UUID4) -> str:
    """Build a short-lived JWT access token with ``sub`` = *user_id*."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: UUID4) -> str:
    """Build a long-lived JWT refresh token with ``sub`` = *user_id*."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


class AuthService:
    """High-level authentication operations executed inside a DB session."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def decode_access_token(token: str) -> dict[str, Any]:
        """Decode and validate a JWT access token.

        Returns the payload dict or raises ``InvalidTokenError``.
        """
        try:
            result: dict[str, Any] = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            return result
        except JWTError:
            raise InvalidTokenError("Invalid or expired token") from None

    def register(
        self, payload: RegisterRequest, background_tasks: BackgroundTasks | None = None
    ) -> RegisterResponse:
        """Create a user, persist to DB, and return a confirmation.

        When *background_tasks* is provided an email verification link
        is sent asynchronously.
        """
        existing = (
            self.db.query(User)
            .filter(User.email == payload.email)
            .first()
        )
        if existing:
            raise EmailAlreadyExistsError()

        user = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            email_verification_token=secrets.token_urlsafe(32),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        if background_tasks is not None:
            background_tasks.add_task(send_activation_email, user)

        return RegisterResponse(email=user.email, full_name=user.full_name)

    def login(self, payload: LoginRequest) -> TokenResponse:
        """Verify credentials and return token pair."""
        user = (
            self.db.query(User)
            .filter(User.email == payload.email)
            .first()
        )
        if not user or not verify_password(payload.password, user.password_hash):
            raise InvalidCredentialsError()

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    def refresh(self, payload: RefreshRequest) -> TokenResponse:
        """Validate refresh token and issue a fresh token pair."""
        tok = payload.refresh_token
        try:
            decoded = jwt.decode(
                tok,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except JWTError:
            raise InvalidTokenError("Invalid or expired refresh token") from None

        user_id_raw: str | None = decoded.get("sub")
        if user_id_raw is None:
            raise InvalidTokenError("Invalid refresh token payload")

        user = (
            self.db.query(User)
            .filter(User.id == uuid.UUID(user_id_raw))
            .first()
        )
        if not user:
            raise UserNotFoundError()

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )
