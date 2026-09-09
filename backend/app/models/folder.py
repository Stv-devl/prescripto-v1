"""Folder model — a single-level folder to organize documents within a project."""

import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Folder(TimestampMixin, Base):
    __tablename__ = "folders"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    lot: Mapped[str] = mapped_column(String(100), default="")
    phase: Mapped[str] = mapped_column(String(50), default="")

    project: Mapped["Project"] = relationship(back_populates="folders")  # type: ignore[name-defined]  # noqa: F821
    documents: Mapped[list["Document"]] = relationship(back_populates="folder")  # type: ignore[name-defined]  # noqa: F821
