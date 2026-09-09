"""Cross-tenant isolation tests for the project summary service.

Every function filters by `Project.tenant_id` in SQL — a `project_id`
belonging to another tenant must never leak a cached summary, the real
document count, or trigger any Mistral/Qdrant call. These cases are the
barrier's only proof.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.project import Project
from app.models.summary import ProjectSummary
from app.models.tenant import Tenant
from app.services import project as project_service
from app.services import summary as summary_service

pytestmark = pytest.mark.asyncio


async def _project_of(db: AsyncSession, tenant: Tenant, name: str = "Chantier") -> Project:
    return await project_service.create_project(db, tenant.id, name=name, phase="PRO")


async def _document_of(
    db: AsyncSession, project: Project, filename: str = "doc.pdf", **kw: object
) -> Document:
    document = Document(project_id=project.id, filename=filename, status="ready", **kw)
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


class TestSummaryIsolation:
    async def test_get_summary_of_another_tenants_project_returns_none(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        cached = ProjectSummary(project_id=project.id, status="done", data_json="{}")
        db.add(cached)
        await db.commit()

        result = await summary_service.get_summary(db, tenant_id=tenant_a.id, project_id=project.id)

        assert result is None

    async def test_get_summary_status_of_another_tenants_project_reports_no_documents(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        await _document_of(db, project, "cctp-1.pdf")
        await _document_of(db, project, "cctp-2.pdf")

        status = await summary_service.get_summary_status(
            db, tenant_id=tenant_a.id, project_id=project.id
        )

        assert status.has_documents is False

    async def test_generate_summary_stream_of_another_tenants_project_yields_no_documents_error(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        await _document_of(db, project, "cctp.pdf")

        agen = summary_service.generate_summary_stream(
            db, tenant_id=tenant_a.id, project_id=project.id
        )
        first = await agen.__anext__()

        assert "Aucun document dans le projet" in first

        await agen.aclose()


class TestRepairingTruncatedJson:
    """Characterisation, written to make a dead-code removal provable.

    `_repair_json` carried a loop whose variable was never read, over a tuple
    that repeated one of its values, so three passes did identical work. These
    cases fix what the function is for — recovering a dict, or admitting it
    cannot — without pinning how much it recovers, which is a separate defect
    measured on the same day and left on the backlog.
    """

    def test_a_truncated_object_comes_back_as_a_dict(self) -> None:
        from app.services.summary import _repair_json

        assert isinstance(_repair_json('{"sections": [{"a": 1}, {"b": 2'), dict)

    def test_an_unterminated_string_comes_back_as_a_dict(self) -> None:
        from app.services.summary import _repair_json

        assert isinstance(_repair_json('{"x": "coupe au milieu'), dict)

    def test_text_that_is_not_json_comes_back_as_none(self) -> None:
        from app.services.summary import _repair_json

        assert _repair_json("pas du json du tout") is None

    def test_an_empty_response_comes_back_as_none(self) -> None:
        from app.services.summary import _repair_json

        assert _repair_json("") is None
