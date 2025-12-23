"""Chat orchestration service."""

import json
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage

from langchain_docker.api.schemas.chat import ChatRequest, ChatResponse, MessageSchema
from langchain_docker.api.services.memory_service import MemoryService
from langchain_docker.api.services.model_service import ModelService
from langchain_docker.api.services.session_service import SessionService
from langchain_docker.core.tracing import trace_session


class ChatService:
    """Service for orchestrating chat interactions.

    Coordinates between session management, memory management, and model invocation.
    """

    def __init__(
        self,
        session_service: SessionService,
        model_service: ModelService,
        memory_service: MemoryService,
    ):
        """Initialize chat service.

        Args:
            session_service: Session management service
            model_service: Model caching service
            memory_service: Memory management service
        """
        self.session_service = session_service
        self.model_service = model_service
        self.memory_service = memory_service

    def process_message(self, request: ChatRequest) -> ChatResponse:
        """Process a chat message (non-streaming).

        Args:
            request: Chat request

        Returns:
            Chat response with AI message
        """
        # Get or create session
        session = self.session_service.get_or_create(request.session_id)

        # Add user message to session
        user_message = HumanMessage(content=request.message)
        session.messages.append(user_message)

        # Process conversation memory (NEW)
        context_messages, memory_metadata = self.memory_service.process_conversation(
            session, request
        )

        # Get model from cache
        model = self.model_service.get_or_create(
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        # Invoke model with optimized context window and session tracing
        with trace_session(session.session_id):
            ai_response = model.invoke(context_messages)

        # Add AI response to session
        session.messages.append(ai_response)

        # Update session timestamp
        self.session_service.update_timestamp(session.session_id)

        # Convert to response schema (with memory metadata)
        return ChatResponse(
            session_id=session.session_id,
            message=MessageSchema.from_langchain(ai_response),
            conversation_length=len(session.messages),
            memory_metadata=memory_metadata,  # NEW
        )

    async def stream_message(self, request: ChatRequest) -> AsyncGenerator[dict, None]:
        """Process a chat message with streaming.

        Args:
            request: Chat request

        Yields:
            Server-Sent Event dicts with event and data keys
        """
        # Get or create session
        session = self.session_service.get_or_create(request.session_id)

        # Add user message to session
        user_message = HumanMessage(content=request.message)
        session.messages.append(user_message)

        # Process conversation memory (NEW)
        context_messages, memory_metadata = self.memory_service.process_conversation(
            session, request
        )

        # Get model from cache
        model = self.model_service.get_or_create(
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        # Send start event (with memory info)
        yield {
            "event": "start",
            "data": json.dumps({
                "session_id": session.session_id,
                "model": request.model or self.model_service._get_default_model(request.provider),
                "provider": request.provider,
                "memory_metadata": memory_metadata.model_dump(mode='json'),  # NEW
            }),
        }

        # Stream response tokens with session tracing
        full_content = ""
        try:
            # Use optimized context window with session tracing
            with trace_session(session.session_id):
                for chunk in model.stream(context_messages):
                    if chunk.content:
                        full_content += chunk.content
                        yield {
                            "event": "token",
                            "data": json.dumps({"content": chunk.content}),
                        }

            # Create AI message from full content
            from langchain_core.messages import AIMessage

            ai_message = AIMessage(content=full_content)
            session.messages.append(ai_message)

            # Update session timestamp
            self.session_service.update_timestamp(session.session_id)

            # Send done event (with memory metadata)
            yield {
                "event": "done",
                "data": json.dumps({
                    "session_id": session.session_id,
                    "conversation_length": len(session.messages),
                    "message": MessageSchema.from_langchain(ai_message).model_dump(mode='json'),
                    "memory_metadata": memory_metadata.model_dump(mode='json'),  # NEW
                }),
            }

        except Exception as e:
            # Send error event
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
