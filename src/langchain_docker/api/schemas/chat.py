"""Chat-related Pydantic schemas."""

from datetime import datetime
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field


class MessageSchema(BaseModel):
    """Schema for a single message."""

    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_langchain(cls, message: BaseMessage) -> "MessageSchema":
        """Convert LangChain message to schema.

        Args:
            message: LangChain BaseMessage

        Returns:
            MessageSchema instance
        """
        if isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        else:
            role = "assistant"  # Default to assistant for unknown types

        metadata = {}
        if hasattr(message, "response_metadata"):
            metadata = message.response_metadata or {}

        return cls(
            role=role,
            content=message.content,
            metadata=metadata,
        )

    def to_langchain(self) -> BaseMessage:
        """Convert schema to LangChain message.

        Returns:
            HumanMessage or AIMessage
        """
        if self.role == "user":
            return HumanMessage(content=self.content)
        else:
            return AIMessage(content=self.content)


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""

    message: str = Field(..., min_length=1, description="User message")
    session_id: str | None = Field(None, description="Session ID for conversation history")
    provider: str = Field("openai", description="Model provider")
    model: str | None = Field(None, description="Model name (uses provider default if not specified)")
    temperature: float = Field(0.0, ge=0.0, le=2.0, description="Temperature for response generation")
    stream: bool = Field(False, description="Enable streaming response")
    max_tokens: int | None = Field(None, gt=0, description="Maximum tokens in response")


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""

    session_id: str
    message: MessageSchema
    conversation_length: int = Field(..., description="Total number of messages in conversation")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StreamEvent(BaseModel):
    """Schema for streaming events."""

    event: Literal["start", "token", "done", "error"]
    data: dict[str, Any]
