"""Chunk model — a text segment extracted from a document, indexed in Qdrant."""

import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Chunk(TimestampMixin, Base):
    """A text segment extracted from a document, indexed in Qdrant.

    The metadata columns below are also stored in Qdrant payloads; they are
    duplicated here for SQL filtering and stats.
    """

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    qdrant_point_id: Mapped[str] = mapped_column(String(255), default="")

    lot: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    phase: Mapped[str | None] = mapped_column(String(50), nullable=True)
    type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    heading_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    section_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_sections: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    localisation: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")  # type: ignore[name-defined]  # noqa: F821
