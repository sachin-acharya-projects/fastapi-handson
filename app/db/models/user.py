"""SQLAlchemy ORM model for the ``User`` entity."""

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, ModelMixin


class User(ModelMixin, Base):
    """Application user — the primary identity and resource model."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Email verification
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    email_verification_token: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Profile picture
    profile_picture_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
