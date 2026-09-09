"""User model — authenticated user belonging to a tenant."""

import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin

DEFAULT_ROLE = "owner"
ADMIN_ROLE = "admin"


class User(TenantMixin, TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default=DEFAULT_ROLE)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email_verified: Mapped[bool] = mapped_column(default=False)
    token_version: Mapped[int] = mapped_column(default=0, server_default="0")

    tenant: Mapped["Tenant"] = relationship(back_populates="users")  # type: ignore[name-defined]  # noqa: F821
    conversations: Mapped[list["Conversation"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )  # type: ignore[name-defined]
