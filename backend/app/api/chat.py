"""Chat API endpoints — SSE streaming and conversation management."""

import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession
from app.schemas.chat import ChatRequest, ConversationList, ConversationRead, MessageRead
from app.services import chat as chat_service

router = APIRouter(tags=["chat"])


@router.post("/projects/{project_id}/chat")
async def chat(
    project_id: uuid.UUID,
    body: ChatRequest,
    db: DbSession,
    user: CurrentUser,
) -> StreamingResponse:
    """Stream a RAG chat response as Server-Sent Events."""
    stream = chat_service.chat_stream(
        db,
        tenant_id=user["tenant_id"],
        project_id=project_id,
        user_id=user["user_id"],
        question=body.message,
        conversation_id=body.conversation_id,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@router.get("/projects/{project_id}/conversations", response_model=ConversationList)
async def list_conversations(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> ConversationList:
    """List all conversations for a project."""
    conversations, total = await chat_service.list_conversations(
        db, tenant_id=user["tenant_id"], project_id=project_id
    )
    return ConversationList(
        conversations=[ConversationRead.model_validate(c) for c in conversations],
        total=total,
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
async def get_messages(
    conversation_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> list[MessageRead]:
    """Get all messages for a conversation."""
    return await chat_service.get_messages(
        db, tenant_id=user["tenant_id"], conversation_id=conversation_id
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> None:
    """Delete a conversation."""
    await chat_service.delete_conversation(
        db, tenant_id=user["tenant_id"], conversation_id=conversation_id
    )
