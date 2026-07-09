"""User CRUD service — create, read, update, delete, and list users.

All database queries live here so endpoints stay free of ORM imports.
Soft-deleted records are excluded from all queries by the session.
"""

import uuid
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from PIL import Image
from pydantic import UUID4
from sqlalchemy import desc as sa_desc
from sqlalchemy import select

from app.core.config import settings
from app.db.models import User
from app.db.session import Session
from app.exceptions.exceptions import (
    EmailAlreadyExistsError,
    InvalidTokenError,
    UserNotFoundError,
)
from app.schemas.user import UserCreationModel, UserUpdateModel
from app.services.auth import hash_password


class UserService:
    """High-level user operations executed inside a DB session."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_user(self, payload: UserCreationModel) -> User:
        """Insert a new user after checking for email uniqueness.

        Raises ``EmailAlreadyExistsError`` (400) when the email is taken.
        """
        existing = self.db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise EmailAlreadyExistsError()

        user = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def retrieve_user(
        self, user_id: UUID4, include_deleted: bool = False
    ) -> User:
        """Return a single user by id.

        Raises ``UserNotFoundError`` (404) if the id does not exist
        or the user has been soft-deleted (unless *include_deleted* is
        ``True``).
        """
        stmt = select(User).where(User.id == user_id)
        if include_deleted:
            stmt = stmt.execution_options(include_deleted=True)
        user = self.db.execute(stmt).scalar_one_or_none()
        if not user:
            raise UserNotFoundError()
        return user

    def update_user(self, user_id: UUID4, payload: UserUpdateModel) -> User:
        """Apply partial updates to a user.

        Only the fields present (not ``None``) are applied.
        Raises ``UserNotFoundError`` (404) if the id does not exist
        or the user has been soft-deleted.
        """
        user = self.retrieve_user(user_id)
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "password":
                user.password_hash = hash_password(value)
            else:
                setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: UUID4, *, hard: bool = False) -> None:
        """Soft-delete (default) or hard-delete a user by id.

        Soft-delete sets ``deleted_at`` to the current timestamp.
        Hard-delete removes the row from the database.

        Raises ``UserNotFoundError`` (404) if the id does not exist
        or the user is already soft-deleted.
        """
        user = self.retrieve_user(user_id, include_deleted=hard)
        if hard:
            self.db.hard_delete(user)
        else:
            self.db.delete(user)
        self.db.commit()

    def verify_email(self, token: str) -> User:
        """Mark a user's email as verified using the activation token.

        Raises ``InvalidTokenError`` (401) if the token is unknown.
        """
        user = (
            self.db.query(User)
            .filter(User.email_verification_token == token)
            .first()
        )
        if not user:
            raise InvalidTokenError("Invalid or expired verification token")
        user.is_email_verified = True
        user.email_verification_token = None
        self.db.commit()
        self.db.refresh(user)
        return user

    @staticmethod
    def _compress_image(file: UploadFile) -> bytes:
        """Compress an uploaded image using Pillow (max 800 px wide)."""
        image = Image.open(file.file)
        image.thumbnail((800, 800))
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue()

    def update_profile_picture(
        self, user_id: uuid.UUID, file: UploadFile
    ) -> User:
        """Compress and store a profile picture, then update the user record."""
        data = self._compress_image(file)
        ext = "jpg"
        filename = f"{user_id}.{ext}"
        upload_path = Path(settings.UPLOAD_DIR)
        upload_path.mkdir(parents=True, exist_ok=True)
        (upload_path / filename).write_bytes(data)

        user = self.retrieve_user(user_id)
        user.profile_picture_url = f"/{settings.UPLOAD_DIR}/{filename}"
        self.db.commit()
        self.db.refresh(user)
        return user

    def list_users(
        self,
        params: Params,
        search: str | None = None,
        is_active: bool | None = None,
        include_deleted: bool = False,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Page[User]:
        """Return a paginated, filterable, sortable list of users.

        Keyword arguments:
          search — case-insensitive substring match on email or name
          is_active — ``True`` / ``False`` to filter by active status
          include_deleted — include soft-deleted records (default ``False``)
          sort_by — column name (``created_at``, ``email``, ``full_name``)
          sort_order — ``asc`` or ``desc`` (default)
        """
        stmt = select(User)

        if include_deleted:
            stmt = stmt.execution_options(include_deleted=True)

        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(
                User.email.ilike(pattern) | User.full_name.ilike(pattern)
            )

        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)

        sort_column = getattr(User, sort_by, User.created_at)
        if sort_order == "desc":
            sort_column = sa_desc(sort_column)
        stmt = stmt.order_by(sort_column)

        return paginate(self.db, stmt, params)
