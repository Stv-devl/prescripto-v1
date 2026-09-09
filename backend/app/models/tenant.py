"""Tenant model — top-level entity for multi-tenant isolation."""

import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(50), default="free")

    users: Mapped[list["User"]] = relationship(  # noqa: F821
        back_populates="tenant", cascade="all, delete-orphan"
    )  # type: ignore[name-defined]
    projects: Mapped[list["Project"]] = relationship(  # noqa: F821
        back_populates="tenant", cascade="all, delete-orphan"
    )  # type: ignore[name-defined]
