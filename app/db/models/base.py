"""SQLAlchemy ``DeclarativeBase`` and reusable mixins used by all ORM models.

Mixins are intentionally granular so models can pick exactly what they need::

    class User(ModelMixin, Base):
        __tablename__ = "users"
        ...

``ModelMixin`` bundles all four mixins — it is the standard choice for most
application models.

**Note on automatic audit fields (django-currentuser equivalent):**
FastAPI has no built-in "current user" middleware like Django's ``CurrentUser``.
The idiomatic approach is to pass the authenticated user explicitly to service
methods::

    def update_user(self, user_id, payload, *, current_user: User) -> User:
        user = self.retrieve_user(user_id)
        user.updated_by = current_user.id
        ...

If you truly want automatic injection, you can use ``request.state`` with a
middleware or a custom dependency, but explicit passing is simpler and more
testable.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Abstract base class for all ORM models."""


class UUIDMixin:
    """Mixin adding a UUID primary key column."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )


class TimestampMixin:
    """Mixin adding ``created_at`` and ``updated_at`` timestamp columns.

    ``created_at`` is set once on insert (via ``server_default=func.now()``).
    ``updated_at`` is refreshed on every update (via ``onupdate=func.now()``).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin adding a ``deleted_at`` column for soft-delete support.

    Rows are never physically removed — callers should filter with
    ``deleted_at.is_(None)`` to exclude soft-deleted records.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuditMixin:
    """Mixin adding ``created_by`` and ``updated_by`` foreign-key columns.

    These store the UUID of the user who created/updated the row.
    Values must be set explicitly in service code — there is no automatic
    "current user" injection (see the ``django-currentuser`` question below).
    """

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )


class ModelMixin(UUIDMixin, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Convenience mixin combining all four base mixins.

    This is the standard choice for most application models::

        class User(ModelMixin, Base):
            __tablename__ = "users"
            ...
    """
