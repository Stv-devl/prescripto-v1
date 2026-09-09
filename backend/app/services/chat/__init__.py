"""Chat service — public API re-exports.

All existing imports like `from app.services.chat import chat_stream`
or `from app.services import chat as chat_service` continue to work.
"""

from app.services.chat.conversation import (
    create_conversation,
    delete_conversation,
    get_conversation,
    get_messages,
    list_conversations,
)
from app.services.chat.prompts import SYSTEM_PROMPT, get_forced_related
from app.services.chat.stream import chat_stream

__all__ = [
    "SYSTEM_PROMPT",
    "chat_stream",
    "create_conversation",
    "delete_conversation",
    "get_conversation",
    "get_forced_related",
    "get_messages",
    "list_conversations",
]
