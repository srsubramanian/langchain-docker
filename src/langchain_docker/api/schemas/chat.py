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


class MemoryMetadata(BaseModel):
    """Metadata about memory management for this response."""

    summarized: bool = Field(False, description="Whether summarization occurred")
    summary_triggered: bool = Field(False, description="Whether trigger threshold was reached")
    total_messages: int = Field(..., description="Total number of messages in conversation")
    summarized_message_count: int = Field(0, description="Number of messages included in summary")
    recent_message_count: int = Field(..., description="Number of recent messages kept intact")
    summary_content: str | None = Field(None, description="The summary text (for debugging)")


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""

    message: str = Field(..., min_length=1, description="User message")
    session_id: str | None = Field(None, description="Session ID for conversation history")
    provider: str = Field("openai", description="Model provider")
    model: str | None = Field(None, description="Model name (uses provider default if not specified)")
    temperature: float = Field(0.0, ge=0.0, le=2.0, description="Temperature for response generation")
    stream: bool = Field(False, description="Enable streaming response")
    max_tokens: int | None = Field(None, gt=0, description="Maximum tokens in response")
    enable_memory: bool = Field(True, description="Enable conversation memory management")
    memory_trigger_count: int | None = Field(None, gt=0, description="Override trigger threshold for summarization")
    memory_keep_recent: int | None = Field(None, gt=0, description="Override number of recent messages to keep")


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""

    session_id: str
    message: MessageSchema
    conversation_length: int = Field(..., description="Total number of messages in conversation")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    memory_metadata: MemoryMetadata | None = Field(None, description="Memory management metadata")


class StreamEvent(BaseModel):
    """Schema for streaming events."""

    event: Literal["start", "token", "done", "error"]
    data: dict[str, Any]
