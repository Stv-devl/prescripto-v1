"""Conversation and message CRUD operations (DB only, no LLM calls)."""

import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.chat import MessageRead, Source, StructuredSchema, StructuredTable
from app.services import project as project_service


async def create_conversation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
) -> Conversation:
    """Create a new conversation in a project."""
    await project_service.get_project(db, tenant_id, project_id)
    conv = Conversation(project_id=project_id, user_id=user_id, title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def get_conversation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> Conversation:
    """Get a conversation by ID, verifying tenant access via its project."""
    query = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(query)
    conv = result.scalar_one_or_none()

    if conv is None:
        raise NotFoundError(f"Conversation {conversation_id} not found")

    await project_service.get_project(db, tenant_id, conv.project_id)
    return conv


async def list_conversations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> tuple[list[Conversation], int]:
    """List all conversations for a project. Returns (conversations, total)."""
    await project_service.get_project(db, tenant_id, project_id)

    query = (
        select(Conversation)
        .where(Conversation.project_id == project_id)
        .order_by(Conversation.updated_at.desc())
    )
    result = await db.execute(query)
    conversations = list(result.scalars().all())

    count_query = (
        select(func.count()).select_from(Conversation).where(Conversation.project_id == project_id)
    )
    total = (await db.execute(count_query)).scalar_one()

    return conversations, total


async def delete_conversation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> None:
    """Delete a conversation by ID, verifying tenant access."""
    conv = await get_conversation(db, tenant_id, conversation_id)
    await db.delete(conv)
    await db.commit()


async def get_messages(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> list[MessageRead]:
    """Get all messages for a conversation, with deserialized sources."""
    await get_conversation(db, tenant_id, conversation_id)

    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    result = await db.execute(query)
    messages = list(result.scalars().all())

    return [_message_to_read(msg) for msg in messages]


def _message_to_read(msg: Message) -> MessageRead:
    """Convert a Message ORM instance to a MessageRead schema with parsed sources."""
    try:
        sources_data = json.loads(msg.sources_json) if msg.sources_json else []
        sources = [Source(**s) for s in sources_data]
    except (json.JSONDecodeError, TypeError):
        sources = []

    structured: StructuredTable | None = None
    if msg.structured_json:
        try:
            structured = StructuredTable(**json.loads(msg.structured_json))
        except (json.JSONDecodeError, TypeError):
            structured = None

    schema: StructuredSchema | None = None
    if msg.schema_json:
        try:
            schema = StructuredSchema(**json.loads(msg.schema_json))
        except (json.JSONDecodeError, TypeError):
            schema = None

    return MessageRead(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        sources=sources,
        structured=structured,
        schema_=schema,
        created_at=msg.created_at,
    )
