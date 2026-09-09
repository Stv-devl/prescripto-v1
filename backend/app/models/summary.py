"""ProjectSummary model — AI-generated project summary cached in DB."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ProjectSummary(TimestampMixin, Base):
    __tablename__ = "project_summaries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, default=uuid.uuid4, primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), default="generating")
    data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="summary")  # type: ignore[name-defined]  # noqa: F821
