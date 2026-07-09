"""SQLAlchemy engine, session factory, and ``get_db`` dependency.

Uses a custom ``SoftDeleteSession`` class that:

* Automatically excludes soft-deleted records from all ``SELECT`` queries.
* Converts ``session.delete(obj)`` into a soft-delete (sets ``deleted_at``)
  for models that have a ``deleted_at`` column.
* Provides ``session.hard_delete(obj)`` for true physical deletion.
* Supports ``include_deleted=True`` as an execution-option escape hatch.

Usage
-----
Inject ``DbSessionDep`` as before — no service code changes needed.
Soft-delete and auto-filtering happen transparently.

To query soft-deleted records, use ``execution_options``::

    stmt = select(User).where(...)
    user = db.execute(stmt, execution_options={"include_deleted": True}).scalar_one()

Or with the legacy ``Query`` API::

    db.query(User).options(execution_options(include_deleted=True)).all()
"""

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import create_engine, event
from sqlalchemy.orm import ORMExecuteState, sessionmaker, with_loader_criteria
from sqlalchemy.orm import Session as SASession

from app.core.config import settings


class SoftDeleteSession(SASession):
    """SQLAlchemy session with automatic soft-delete support.

    - ``session.delete(obj)`` → sets ``obj.deleted_at`` (soft).
    - ``session.hard_delete(obj)`` → physical delete (original behaviour).
    """

    def delete(self, instance: Any) -> None:
        """Soft-delete *instance* if it has a ``deleted_at`` column."""
        if hasattr(instance, "deleted_at"):
            instance.deleted_at = datetime.now(UTC)
        else:
            super().delete(instance)

    def hard_delete(self, instance: Any) -> None:
        """Physically remove *instance* from the database."""
        super().delete(instance)


Session = SoftDeleteSession
"""Type alias — points to ``SoftDeleteSession`` so that ``hard_delete`` is
visible to type checkers when services import ``Session`` from this module."""

__all__ = [
    "DbSessionDep",
    "Session",
    "SessionLocal",
    "SoftDeleteSession",
    "engine",
    "get_db",
]

engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(
    class_=SoftDeleteSession,
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@event.listens_for(SoftDeleteSession, "do_orm_execute")
def _add_soft_delete_filter(execute_state: ORMExecuteState) -> None:
    """Automatically append ``WHERE deleted_at IS NULL`` to SELECT queries.

    Bypass this filter by passing ``include_deleted=True`` in
    ``execution_options``, for example::

        db.execute(stmt, execution_options={"include_deleted": True})
    """
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get("include_deleted"):
        return

    from app.db.models.base import SoftDeleteMixin  # noqa: PLC0415

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.deleted_at.is_(None),
            include_aliases=True,
        ),
    )


def get_db() -> Generator[Session, None, None]:
    """Yield a scoped ``SoftDeleteSession``; roll back on unhandled errors.

    The session is always closed after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


DbSessionDep = Annotated[Session, Depends(get_db)]
"""Injectable dependency that yields a scoped ``SoftDeleteSession``.

Soft-deleted records are excluded from all queries by default.
Pass ``execution_options={"include_deleted": True}`` to bypass.
"""
