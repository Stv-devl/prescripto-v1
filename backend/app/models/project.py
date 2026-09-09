"""Project model — a construction project owned by a tenant."""

import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class Project(TenantMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    phase: Mapped[str] = mapped_column(String(50), default="")
    status: Mapped[str] = mapped_column(String(50), default="active")
    address: Mapped[str] = mapped_column(String(500), default="")
    client: Mapped[str] = mapped_column(String(255), default="")
    architect: Mapped[str] = mapped_column(String(255), default="")
    architect_address: Mapped[str] = mapped_column(String(500), default="")
    bureau_thermique: Mapped[str] = mapped_column(String(255), default="")
    bureau_thermique_address: Mapped[str] = mapped_column(String(500), default="")
    bureau_vrd: Mapped[str] = mapped_column(String(255), default="")
    bureau_vrd_address: Mapped[str] = mapped_column(String(500), default="")
    bureau_beton: Mapped[str] = mapped_column(String(255), default="")
    bureau_beton_address: Mapped[str] = mapped_column(String(500), default="")
    economiste: Mapped[str] = mapped_column(String(255), default="")
    economiste_address: Mapped[str] = mapped_column(String(500), default="")
    controleur_technique: Mapped[str] = mapped_column(String(255), default="")
    controleur_technique_address: Mapped[str] = mapped_column(String(500), default="")
    is_favorite: Mapped[bool] = mapped_column(default=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="projects")  # type: ignore[name-defined]  # noqa: F821
    documents: Mapped[list["Document"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )  # type: ignore[name-defined]
    folders: Mapped[list["Folder"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )  # type: ignore[name-defined]
    conversations: Mapped[list["Conversation"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )  # type: ignore[name-defined]
    summary: Mapped["ProjectSummary | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
