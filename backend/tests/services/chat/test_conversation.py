"""The conversation service — 134 lines that had no test at all.

Every one of its functions delegates its tenant check to `project_service.get_project`,
directly or through `get_conversation`. That indirection is what these cases pin:
a conversation is reachable only through a project the caller owns.

`_message_to_read` degrades instead of raising when a stored JSON column cannot
be parsed — a message written by an older version must not take the whole thread
down with it.
"""

import json
import uuid
from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.user import User
from app.services import project as project_service
from app.services.chat import conversation as conversation_service

pytestmark = pytest.mark.asyncio


async def _user_of(db: AsyncSession, tenant: Tenant, email: str = "eco@cabinet.fr") -> User:
    """A user of the given tenant — conversations carry their author."""
    user = User(tenant_id=tenant.id, email=email, hashed_password="not-a-real-hash")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _project_of(db: AsyncSession, tenant: Tenant, name: str = "Chantier") -> Project:
    return await project_service.create_project(db, tenant.id, name=name, phase="PRO")


async def _message_in(
    db: AsyncSession,
    conversation: Conversation,
    content: str,
    *,
    sources_json: str = "[]",
    structured_json: str | None = None,
    schema_json: str | None = None,
    created_at: datetime | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        sources_json=sources_json,
        structured_json=structured_json,
        schema_json=schema_json,
    )
    db.add(message)
    await db.commit()
    if created_at is not None:
        # SQLite's CURRENT_TIMESTAMP has one-second resolution, so rows written
        # in a row share a timestamp and an ordering assertion would pass on
        # scan order rather than on the ORDER BY.
        message.created_at = created_at
        await db.commit()
    await db.refresh(message)
    return message


async def _conversation_count(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(Conversation))).scalar_one()


class TestConversationCrud:
    async def test_create_conversation_attaches_it_to_the_project(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        user = await _user_of(db, tenant_a)

        conv = await conversation_service.create_conversation(
            db, tenant_a.id, project.id, user.id, "Fondations"
        )

        assert conv.project_id == project.id
        assert conv.user_id == user.id
        assert conv.title == "Fondations"

    async def test_get_conversation_returns_one_of_the_callers_project(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        user = await _user_of(db, tenant_a)
        created = await conversation_service.create_conversation(
            db, tenant_a.id, project.id, user.id, "Fondations"
        )

        fetched = await conversation_service.get_conversation(db, tenant_a.id, created.id)

        assert fetched.id == created.id
        assert fetched.title == "Fondations"

    async def test_list_conversations_orders_most_recently_updated_first(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        user = await _user_of(db, tenant_a)
        stamps = [
            datetime(2026, 1, 1, 10, 0, 0),
            datetime(2026, 1, 2, 10, 0, 0),
            datetime(2026, 1, 3, 10, 0, 0),
        ]
        for title, when in zip(("c1", "c2", "c3"), stamps, strict=True):
            conv = await conversation_service.create_conversation(
                db, tenant_a.id, project.id, user.id, title
            )
            conv.updated_at = when
            await db.commit()

        conversations, _ = await conversation_service.list_conversations(
            db, tenant_a.id, project.id
        )

        assert [c.title for c in conversations] == ["c3", "c2", "c1"]

    async def test_list_conversations_total_counts_exactly_what_it_returns(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        other = await _project_of(db, tenant_a, "Autre chantier")
        user = await _user_of(db, tenant_a)
        for title in ("un", "deux"):
            await conversation_service.create_conversation(
                db, tenant_a.id, project.id, user.id, title
            )
        await conversation_service.create_conversation(
            db, tenant_a.id, other.id, user.id, "ailleurs"
        )

        conversations, total = await conversation_service.list_conversations(
            db, tenant_a.id, project.id
        )

        assert total == len(conversations) == 2

    async def test_delete_conversation_removes_it_and_a_later_get_is_not_found(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        user = await _user_of(db, tenant_a)
        conv = await conversation_service.create_conversation(
            db, tenant_a.id, project.id, user.id, "Éphémère"
        )

        await conversation_service.delete_conversation(db, tenant_a.id, conv.id)

        with pytest.raises(NotFoundError):
            await conversation_service.get_conversation(db, tenant_a.id, conv.id)

    async def test_get_messages_returns_them_in_chronological_order(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        user = await _user_of(db, tenant_a)
        conv = await conversation_service.create_conversation(
            db, tenant_a.id, project.id, user.id, "Fil"
        )
        await _message_in(db, conv, "troisième", created_at=datetime(2026, 1, 3, 10, 0, 0))
        await _message_in(db, conv, "premier", created_at=datetime(2026, 1, 1, 10, 0, 0))
        await _message_in(db, conv, "deuxième", created_at=datetime(2026, 1, 2, 10, 0, 0))

        messages = await conversation_service.get_messages(db, tenant_a.id, conv.id)

        assert [m.content for m in messages] == ["premier", "deuxième", "troisième"]


class TestConversationIsolation:
    async def test_get_conversation_of_another_tenants_project_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        user = await _user_of(db, tenant_b, "b@cabinet.fr")
        foreign = await conversation_service.create_conversation(
            db, tenant_b.id, project.id, user.id, "Secret"
        )

        with pytest.raises(ForbiddenError):
            await conversation_service.get_conversation(db, tenant_a.id, foreign.id)

    async def test_get_conversation_unknown_id_is_not_found(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        with pytest.raises(NotFoundError):
            await conversation_service.get_conversation(db, tenant_a.id, uuid.uuid4())

    async def test_create_conversation_in_another_tenants_project_creates_nothing(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        user = await _user_of(db, tenant_a)

        with pytest.raises(ForbiddenError):
            await conversation_service.create_conversation(
                db, tenant_a.id, project.id, user.id, "Intrusion"
            )

        assert await _conversation_count(db) == 0

    async def test_delete_conversation_of_another_tenant_leaves_the_row(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        user = await _user_of(db, tenant_b, "b@cabinet.fr")
        foreign = await conversation_service.create_conversation(
            db, tenant_b.id, project.id, user.id, "Secret"
        )

        with pytest.raises(ForbiddenError):
            await conversation_service.delete_conversation(db, tenant_a.id, foreign.id)

        assert await _conversation_count(db) == 1

    async def test_list_conversations_of_another_tenants_project_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """The listing query filters on `project_id` alone.

        Its only tenant key is the `get_project` call above it, so without this
        case that guard could be deleted and tenant A would enumerate the
        conversations of a project belonging to B — titles included — with the
        whole suite still green.
        """
        project = await _project_of(db, tenant_b, "Secret de B")
        user = await _user_of(db, tenant_b, "b@cabinet.fr")
        await conversation_service.create_conversation(
            db, tenant_b.id, project.id, user.id, "Secret"
        )

        with pytest.raises(ForbiddenError):
            await conversation_service.list_conversations(db, tenant_a.id, project.id)

    async def test_get_messages_of_another_tenants_conversation_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """Same shape one level down: the message query filters on `conversation_id`
        alone, and its only tenant key is the `get_conversation` call above it."""
        project = await _project_of(db, tenant_b, "Secret de B")
        user = await _user_of(db, tenant_b, "b@cabinet.fr")
        foreign = await conversation_service.create_conversation(
            db, tenant_b.id, project.id, user.id, "Secret"
        )
        await _message_in(db, foreign, "contenu confidentiel")

        with pytest.raises(ForbiddenError):
            await conversation_service.get_messages(db, tenant_a.id, foreign.id)

    async def test_get_messages_never_returns_a_message_of_another_conversation(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        user = await _user_of(db, tenant_a)
        mine = await conversation_service.create_conversation(
            db, tenant_a.id, project.id, user.id, "Le mien"
        )
        other = await conversation_service.create_conversation(
            db, tenant_a.id, project.id, user.id, "L'autre"
        )
        await _message_in(db, mine, "à moi")
        await _message_in(db, other, "à l'autre")

        messages = await conversation_service.get_messages(db, tenant_a.id, mine.id)

        assert [m.content for m in messages] == ["à moi"]


class TestMessageDegradation:
    async def test_unparsable_sources_json_reads_as_no_sources(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        user = await _user_of(db, tenant_a)
        conv = await conversation_service.create_conversation(
            db, tenant_a.id, project.id, user.id, "Fil"
        )
        await _message_in(db, conv, "réponse", sources_json="{not json at all")

        messages = await conversation_service.get_messages(db, tenant_a.id, conv.id)

        assert messages[0].sources == []
        assert messages[0].content == "réponse"

    async def test_unparsable_structured_json_reads_as_none(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        user = await _user_of(db, tenant_a)
        conv = await conversation_service.create_conversation(
            db, tenant_a.id, project.id, user.id, "Fil"
        )
        await _message_in(db, conv, "réponse", structured_json="{truncated")

        messages = await conversation_service.get_messages(db, tenant_a.id, conv.id)

        assert messages[0].structured is None

    async def test_unparsable_schema_json_reads_as_none(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        user = await _user_of(db, tenant_a)
        conv = await conversation_service.create_conversation(
            db, tenant_a.id, project.id, user.id, "Fil"
        )
        await _message_in(db, conv, "réponse", schema_json="{truncated")

        messages = await conversation_service.get_messages(db, tenant_a.id, conv.id)

        assert messages[0].schema_ is None

    async def test_a_well_formed_structured_table_survives_the_round_trip(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """Without this, replacing the whole parse block by `structured = None`
        keeps the suite green: line coverage counts the branch as walked even
        though it never once succeeds."""
        project = await _project_of(db, tenant_a)
        user = await _user_of(db, tenant_a)
        conv = await conversation_service.create_conversation(
            db, tenant_a.id, project.id, user.id, "Fil"
        )
        table = {
            "title": "Ouvrages",
            "columns": ["Désignation", "Quantité"],
            "rows": [{"Désignation": "Semelle filante", "Quantité": "25 ml"}],
        }
        await _message_in(db, conv, "réponse", structured_json=json.dumps(table))

        messages = await conversation_service.get_messages(db, tenant_a.id, conv.id)

        assert messages[0].structured is not None
        assert messages[0].structured.title == "Ouvrages"
        assert messages[0].structured.rows[0]["Quantité"] == "25 ml"

    async def test_a_well_formed_schema_survives_the_round_trip(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        user = await _user_of(db, tenant_a)
        conv = await conversation_service.create_conversation(
            db, tenant_a.id, project.id, user.id, "Fil"
        )
        schema = {
            "schema_type": "plancher",
            "title": "Plancher haut RDC",
            "params": {"epaisseur": "20 cm"},
        }
        await _message_in(db, conv, "réponse", schema_json=json.dumps(schema))

        messages = await conversation_service.get_messages(db, tenant_a.id, conv.id)

        assert messages[0].schema_ is not None
        assert messages[0].schema_.schema_type == "plancher"
        assert messages[0].schema_.params["epaisseur"] == "20 cm"

    async def test_a_well_formed_source_survives_the_round_trip(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """The degradation cases only mean something if the happy path works."""
        project = await _project_of(db, tenant_a)
        user = await _user_of(db, tenant_a)
        conv = await conversation_service.create_conversation(
            db, tenant_a.id, project.id, user.id, "Fil"
        )
        source = {
            "document_id": str(uuid.uuid4()),
            "filename": "cctp.pdf",
            "page": 3,
            "lot": "03 - Maçonnerie",
            "phase": "PRO",
            "text": "Béton C25/30",
        }
        await _message_in(db, conv, "réponse", sources_json=json.dumps([source]))

        messages = await conversation_service.get_messages(db, tenant_a.id, conv.id)

        assert len(messages[0].sources) == 1
        assert messages[0].sources[0].filename == "cctp.pdf"
