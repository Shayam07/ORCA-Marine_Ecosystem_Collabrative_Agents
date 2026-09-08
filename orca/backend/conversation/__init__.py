"""ORCA Conversation Module."""

from .manager import ConversationManager, ConversationContext, ConversationMessage, get_conversation_manager
from .resolver import ContextResolver
from .language import detect_language, get_language_name, get_response_text

__all__ = [
    "ConversationManager",
    "ConversationContext",
    "ConversationMessage",
    "get_conversation_manager",
    "ContextResolver",
    "detect_language",
    "get_language_name",
    "get_response_text",
]
