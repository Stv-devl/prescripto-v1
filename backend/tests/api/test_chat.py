"""HTTP-level proof that the LangGraph-orchestrated chat_stream() produces the
same SSE contract as the endpoint always advertised — AC5 of J1
(docs/work/j1-langgraph-orchestration/plan.md).

`httpx.AsyncClient` over `ASGITransport`, same reasoning as test_admin.py: the
`db` fixture's SQLite connection belongs to this event loop, and the lifespan
must not run (it reaches for a real Postgres).
"""

import json
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.mistral import mistral_client
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User
from app.services import project as project_service
from tests.fakes import FakePoint, FakeQdrant

QUESTION = "Quel est le type de béton utilisé pour les fondations ?"
CHUNK_TEXT = (
    "Les semelles filantes de ce chantier sont coulées en béton armé C25/30, "
    "avec une largeur de cinquante centimètres et une hauteur de vingt centimètres."
)


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


async def _authed_user(db: AsyncSession, tenant: Tenant) -> User:
    user = User(
        tenant_id=tenant.id,
        email=f"eco-{uuid.uuid4()}@cabinet.fr",
        hashed_password="not-a-real-hash",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _override_current_user(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": user.id,
        "tenant_id": user.tenant_id,
    }


def _rewrite_response() -> SimpleNamespace:
    content = json.dumps({"query": QUESTION, "related": [], "structured": "none", "schema": "none"})
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=None
    )


class TestChatEndpointSseContract:
    async def test_happy_path_streams_conversation_id_text_sources_usage_done(
        self, client: AsyncClient, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await project_service.create_project(
            db, tenant_a.id, name="Chantier", phase="PRO"
        )
        user = await _authed_user(db, tenant_a)
        _override_current_user(user)

        fake = FakeQdrant(
            [
                FakePoint(
                    id=str(uuid.uuid4()),
                    score=0.9,
                    payload={
                        "tenant_id": str(tenant_a.id),
                        "project_id": str(project.id),
                        "document_id": str(uuid.uuid4()),
                        "text": CHUNK_TEXT,
                        "page": 12,
                        "position": 5,
                        "filename": "CCTP_fondations.pdf",
                        "lot": "01 - Gros oeuvre",
                        "phase": "PRO",
                        "type": "CCTP",
                        "content_type": "description",
                    },
                )
            ]
        )

        async def _complete_async(*, model: str, messages: list[dict[str, str]], **kwargs: object):
            return _rewrite_response()

        def _stream_async(*, model: str, messages: list[dict[str, str]], **kwargs: object):
            async def _gen() -> object:
                for token in ("Les fondations ", "sont en béton armé."):
                    yield SimpleNamespace(
                        data=SimpleNamespace(
                            choices=[SimpleNamespace(delta=SimpleNamespace(content=token))],
                            usage=None,
                        )
                    )

            return _gen()

        async def _create_async(*, model: str, inputs: list[str], **kwargs: object):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0, 0.0]) for _ in inputs])

        with (
            patch("app.services.search.qdrant_client", fake),
            patch("app.services.chat.chunk_enrichment.qdrant_client", fake),
            patch("app.services.chat.context_enrichment.qdrant_client", fake),
            patch.object(mistral_client.chat, "complete_async", side_effect=_complete_async),
            patch.object(mistral_client.chat, "stream_async", side_effect=_stream_async),
            patch.object(mistral_client.embeddings, "create_async", side_effect=_create_async),
        ):
            async with client.stream(
                "POST",
                f"/api/projects/{project.id}/chat",
                json={"message": QUESTION},
            ) as response:
                assert response.status_code == 200
                lines = [line async for line in response.aiter_lines() if line]

        events = []
        for line in lines:
            assert line.startswith("data: ")
            payload = line[len("data: ") :]
            events.append("DONE" if payload == "[DONE]" else json.loads(payload))

        kinds = ["DONE" if e == "DONE" else next(iter(e)) for e in events]
        assert kinds == ["conversation_id", "text", "text", "sources", "usage", "DONE"]
        assert events[1]["text"] + events[2]["text"] == "Les fondations sont en béton armé."
        assert events[3]["sources"][0]["filename"] == "CCTP_fondations.pdf"
        assert set(events[4]["usage"].keys()) == {"rewrite", "generation", "total"}

    async def test_search_failure_streams_error_then_done(
        self, client: AsyncClient, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await project_service.create_project(
            db, tenant_a.id, name="Chantier", phase="PRO"
        )
        user = await _authed_user(db, tenant_a)
        _override_current_user(user)

        raising_qdrant = MagicMock()
        raising_qdrant.search = AsyncMock(side_effect=RuntimeError("Qdrant unreachable"))

        async def _complete_async(*, model: str, messages: list[dict[str, str]], **kwargs: object):
            return _rewrite_response()

        with (
            patch("app.services.search.qdrant_client", raising_qdrant),
            patch("app.services.chat.chunk_enrichment.qdrant_client", raising_qdrant),
            patch("app.services.chat.context_enrichment.qdrant_client", raising_qdrant),
            patch.object(mistral_client.chat, "complete_async", side_effect=_complete_async),
        ):
            async with client.stream(
                "POST",
                f"/api/projects/{project.id}/chat",
                json={"message": QUESTION},
            ) as response:
                assert response.status_code == 200
                lines = [line async for line in response.aiter_lines() if line]

        events = []
        for line in lines:
            payload = line[len("data: ") :]
            events.append("DONE" if payload == "[DONE]" else json.loads(payload))

        kinds = ["DONE" if e == "DONE" else next(iter(e)) for e in events]
        assert kinds == ["conversation_id", "error", "DONE"]
        assert "temporairement indisponible" in events[1]["error"]
