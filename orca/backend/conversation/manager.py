"""ORCA Conversation Manager — Multi-turn context retention.

Maintains conversation state across messages so the user doesn't
have to repeat information. Supports dynamic geography, intent
continuity, and follow-up interpretation.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("orca.conversation")


class ConversationContext(BaseModel):
    """Persistent context for a conversation thread."""

    conversation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "anonymous"
    language: str = "en"

    # Location context
    current_location_name: Optional[str] = None
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    current_bbox: Optional[list[float]] = None  # [west, south, east, north]
    current_region: Optional[str] = None  # e.g. "Bay of Bengal"
    current_environment: Optional[str] = "COASTAL"
    current_fishing_type: Optional[str] = "MARINE"
    current_state: Optional[str] = None
    current_waterbodies: list[dict[str, Any]] = Field(default_factory=list)
    current_clarification: Optional[str] = None

    # Time context
    current_time_range: Optional[tuple[datetime, datetime]] = None
    time_preset: Optional[str] = None  # "today", "tomorrow", "this_week"

    # Intent context
    current_intent: Optional[str] = None
    previous_intents: list[str] = Field(default_factory=list)
    original_query: Optional[str] = None  # The first substantive query

    # Analysis context
    current_analysis_id: Optional[str] = None
    previous_results: list[dict[str, Any]] = Field(default_factory=list)
    candidate_locations: list[dict[str, Any]] = Field(default_factory=list)

    # UI context
    selected_layers: list[str] = Field(default_factory=list)
    map_center: Optional[list[float]] = None
    map_zoom: int = 6

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_message_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def update_location(self, name: str, lat: float, lon: float, bbox: list[float] | None = None, **kwargs):
        """Update the conversation's location context and overwrite previous location."""
        self.current_location_name = name
        self.current_lat = lat
        self.current_lon = lon
        self.current_bbox = bbox or [lon - 1.5, lat - 1.5, lon + 1.5, lat + 1.5]
        self.current_environment = kwargs.get("environment", "COASTAL")
        self.current_fishing_type = kwargs.get("fishing_type", "MARINE")
        self.current_state = kwargs.get("state")
        self.current_waterbodies = kwargs.get("waterbodies", [])
        self.current_clarification = kwargs.get("clarification_needed")
        self.last_message_at = datetime.now(timezone.utc)
        logger.info(f"Context location updated: location={name} ({lat:.2f}, {lon:.2f}), env={self.current_environment}")

    def update_time(self, time_range: tuple[datetime, datetime], preset: str | None = None):
        """Update the conversation's time context."""
        self.current_time_range = time_range
        self.time_preset = preset
        self.last_message_at = datetime.now(timezone.utc)
        logger.info(f"Context updated: time={preset or time_range}")

    def update_intent(self, intent: str):
        """Update the conversation's intent context."""
        if self.current_intent and self.current_intent != intent:
            self.previous_intents.append(self.current_intent)
        self.current_intent = intent
        self.last_message_at = datetime.now(timezone.utc)

    def has_location(self) -> bool:
        return self.current_lat is not None and self.current_lon is not None

    def has_time(self) -> bool:
        return self.current_time_range is not None

    def is_expired(self, max_age_minutes: int = 120) -> bool:
        """Check if the conversation context has expired."""
        age = datetime.now(timezone.utc) - self.last_message_at
        return age > timedelta(minutes=max_age_minutes)

    def to_summary(self) -> str:
        """Generate a human-readable summary of the current context."""
        parts = []
        if self.current_location_name:
            parts.append(f"Location: {self.current_location_name}")
        if self.current_time_range:
            parts.append(f"Time: {self.time_preset or 'custom range'}")
        if self.current_intent:
            parts.append(f"Intent: {self.current_intent}")
        return " | ".join(parts) if parts else "No context established"


class ConversationMessage(BaseModel):
    """A single message in a conversation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str  # "user" or "assistant"
    content: str
    intent: Optional[str] = None
    location: Optional[str] = None
    time_range: Optional[str] = None
    agent_results: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    response_type: str = "text"  # text, fishing_recommendation, safety_alert, etc.
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ConversationManager:
    """Manages conversation state and context.

    In-memory implementation. Replace with Redis/database for production.
    """

    def __init__(self):
        self._conversations: dict[str, ConversationContext] = {}
        self._messages: dict[str, list[ConversationMessage]] = {}

    def get_or_create(self, conversation_id: str | None = None) -> ConversationContext:
        """Get an existing conversation or create a new one."""
        if conversation_id and conversation_id in self._conversations:
            ctx = self._conversations[conversation_id]
            if ctx.is_expired():
                logger.info(f"Conversation {conversation_id} expired, creating new one")
                ctx = ConversationContext(conversation_id=conversation_id)
                self._conversations[conversation_id] = ctx
                self._messages[conversation_id] = []
            return ctx

        ctx = ConversationContext(
            conversation_id=conversation_id or str(uuid.uuid4())
        )
        self._conversations[ctx.conversation_id] = ctx
        self._messages[ctx.conversation_id] = []
        return ctx

    def add_message(self, conversation_id: str, message: ConversationMessage):
        """Add a message to a conversation."""
        if conversation_id not in self._messages:
            self._messages[conversation_id] = []
        self._messages[conversation_id].append(message)

        # Update context from user messages
        if message.role == "user":
            ctx = self.get_or_create(conversation_id)
            ctx.last_message_at = datetime.now(timezone.utc)
            if message.intent:
                ctx.update_intent(message.intent)

    def get_messages(self, conversation_id: str, limit: int = 20) -> list[ConversationMessage]:
        """Get recent messages from a conversation."""
        msgs = self._messages.get(conversation_id, [])
        return msgs[-limit:]

    def get_context(self, conversation_id: str) -> ConversationContext:
        """Get the current context for a conversation."""
        return self.get_or_create(conversation_id)

    def list_conversations(self, user_id: str = "anonymous") -> list[ConversationContext]:
        """List all active conversations for a user."""
        return [
            ctx for ctx in self._conversations.values()
            if ctx.user_id == user_id and not ctx.is_expired()
        ]


# Singleton
_manager: ConversationManager | None = None


def get_conversation_manager() -> ConversationManager:
    global _manager
    if _manager is None:
        _manager = ConversationManager()
    return _manager
