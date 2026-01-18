"""Memory management service for conversation summarization."""

import logging
import threading
from datetime import datetime

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from langchain_docker.api.schemas.chat import ChatRequest, MemoryMetadata
from langchain_docker.api.services.model_service import ModelService
from langchain_docker.api.services.session_service import Session
from langchain_docker.core.config import Config
from langchain_docker.core.tracing import get_tracer, trace_operation

# Configure logging
logger = logging.getLogger(__name__)

# Summarization prompt template
SUMMARIZATION_PROMPT = """You are a conversation summarizer. Your task is to create a concise summary of the conversation history provided below.

The summary should:
1. Capture key facts, context, and decisions made
2. Preserve important user preferences and information
3. Maintain chronological flow of major topics
4. Be concise but comprehensive (2-5 paragraphs maximum)
5. Use third-person perspective ("The user mentioned..." "The assistant explained...")

Important: Do NOT include the most recent {keep_recent} messages in your summary, as those will be kept separately.

Conversation to summarize:
{conversation}

Provide ONLY the summary, no preamble or meta-commentary."""


class MemoryService:
    """Service for managing conversation memory through summarization.

    This service implements a rolling window approach: keep the N most recent
    messages intact, summarize older messages into a SystemMessage.
    """

    def __init__(self, config: Config, model_service: ModelService):
        """Initialize memory service.

        Args:
            config: Application configuration
            model_service: Model service for LLM access
        """
        self.config = config
        self.model_service = model_service
        self._lock = threading.Lock()

    def process_conversation(
        self, session: Session, request: ChatRequest
    ) -> tuple[list[BaseMessage], MemoryMetadata]:
        """Process conversation and return optimized message list.

        Args:
            session: Current conversation session
            request: Chat request with optional memory overrides

        Returns:
            Tuple of (context_messages, memory_metadata)
        """
        with self._lock:
            # Check if we should summarize
            should_summarize = self._should_summarize(session, request)

            # Initialize metadata
            metadata = MemoryMetadata(
                summarized=False,
                summary_triggered=should_summarize,
                total_messages=len(session.messages),
                summarized_message_count=session.summary_message_count,
                recent_message_count=0,
                summary_content=None,
            )

            if should_summarize:
                # Determine how many messages to keep recent
                keep_recent = (
                    request.memory_keep_recent or self.config.memory_keep_recent_count
                )

                # Filter out old SystemMessages (summaries)
                real_messages = [
                    m for m in session.messages if not isinstance(m, SystemMessage)
                ]

                # Split into messages to summarize and messages to keep
                messages_to_summarize = (
                    real_messages[:-keep_recent] if len(real_messages) > keep_recent else []
                )

                if messages_to_summarize:
                    try:
                        # Generate new summary
                        new_summary = self._summarize_messages(
                            messages_to_summarize, request.provider, request.model, session.session_id
                        )

                        # Update session
                        session.conversation_summary = new_summary
                        session.summary_message_count = len(messages_to_summarize)
                        session.last_summarized_at = datetime.utcnow()

                        # Update metadata
                        metadata.summarized = True
                        metadata.summarized_message_count = len(messages_to_summarize)
                        metadata.summary_content = (
                            new_summary[:200] + "..."
                            if len(new_summary) > 200
                            else new_summary
                        )

                        logger.info(
                            f"Summarized {len(messages_to_summarize)} messages for session {session.session_id}"
                        )

                    except Exception as e:
                        logger.error(f"Summarization failed: {e}", exc_info=True)
                        # Don't fail the request, just skip summarization
                        # Use fallback summary if we don't have one yet
                        if not session.conversation_summary:
                            session.conversation_summary = self._create_fallback_summary(
                                messages_to_summarize
                            )
                            session.summary_message_count = len(messages_to_summarize)
                            session.last_summarized_at = datetime.utcnow()
                            metadata.summarized = True
                            metadata.summarized_message_count = len(messages_to_summarize)

            # Build final context window
            context_messages = self._build_context_window(session, request)

            # Update metadata with actual recent count
            real_context = [m for m in context_messages if not isinstance(m, SystemMessage)]
            metadata.recent_message_count = len(real_context)

            return context_messages, metadata

    def _should_summarize(self, session: Session, request: ChatRequest) -> bool:
        """Determine if summarization should occur.

        Args:
            session: Current session
            request: Chat request

        Returns:
            True if summarization should be triggered
        """
        # Check if memory is enabled
        memory_enabled = (
            request.enable_memory if hasattr(request, "enable_memory") else True
        )
        if not memory_enabled or not self.config.memory_enabled:
            return False

        # Get trigger threshold (per-request override or global config)
        trigger_count = (
            request.memory_trigger_count or self.config.memory_trigger_message_count
        )

        # Count real messages (exclude SystemMessages which are summaries)
        real_messages = [m for m in session.messages if not isinstance(m, SystemMessage)]

        # Don't summarize if too few messages (need at least 4 messages = 2 turns)
        if len(real_messages) < 4:
            return False

        # Trigger if we exceed threshold
        return len(real_messages) >= trigger_count

    def _summarize_messages(
        self, messages: list[BaseMessage], provider: str, model: str | None, session_id: str
    ) -> str:
        """Generate summary using LLM.

        Args:
            messages: Messages to summarize
            provider: Model provider for summarization
            model: Model name for summarization
            session_id: Session ID for tracing

        Returns:
            Summary text

        Raises:
            Exception: If summarization fails
        """
        # Get tracer for custom spans
        tracer = get_tracer()

        # Check if messages are too short to bother summarizing
        total_content_length = sum(len(m.content) for m in messages)
        if total_content_length < 500:  # Arbitrary threshold
            # Not worth summarizing, create simple fallback
            return self._create_fallback_summary(messages)

        # Determine which model to use for summarization
        summary_provider = self.config.memory_summarization_provider or provider
        summary_model = self.config.memory_summarization_model or model

        # Get model instance (may use cheaper model for summarization)
        summarization_model = self.model_service.get_or_create(
            provider=summary_provider,
            model=summary_model,
            temperature=self.config.memory_summarization_temperature,
        )

        # Format conversation history
        conversation_text = self._format_messages_for_summary(messages)

        # Build prompt
        prompt = SUMMARIZATION_PROMPT.format(
            keep_recent=self.config.memory_keep_recent_count, conversation=conversation_text
        )

        # Generate summary with enhanced tracing
        with trace_operation(
            session_id=session_id,
            operation="memory_summarize",
            metadata={
                "message_count": len(messages),
                "content_length": total_content_length,
                "provider": summary_provider,
                "model": summary_model,
            },
            tags=["memory", "summarization", summary_provider],
        ):
            # Add custom span for better visibility in Phoenix
            if tracer:
                with tracer.start_as_current_span("memory.summarize") as span:
                    span.set_attribute("message_count", len(messages))
                    span.set_attribute("content_length", total_content_length)
                    span.set_attribute("provider", summary_provider)
                    summary_response = summarization_model.invoke(
                        [HumanMessage(content=prompt)],
                        config={"metadata": {"session_id": session_id, "operation": "summarization"}}
                    )
                    span.set_attribute("summary_length", len(summary_response.content))
            else:
                summary_response = summarization_model.invoke(
                    [HumanMessage(content=prompt)],
                    config={"metadata": {"session_id": session_id, "operation": "summarization"}}
                )

        # Check if summary is too long and condense if needed
        MAX_SUMMARY_LENGTH = 2000  # characters
        if len(summary_response.content) > MAX_SUMMARY_LENGTH:
            logger.warning(f"Summary too long ({len(summary_response.content)} chars), condensing...")
            condense_prompt = f"Please condense this summary to under {MAX_SUMMARY_LENGTH} characters:\n\n{summary_response.content}"
            with trace_operation(
                session_id=session_id,
                operation="memory_condense",
                metadata={"original_length": len(summary_response.content)},
                tags=["memory", "condense", summary_provider],
            ):
                if tracer:
                    with tracer.start_as_current_span("memory.condense") as span:
                        span.set_attribute("original_length", len(summary_response.content))
                        condensed = summarization_model.invoke(
                            [HumanMessage(content=condense_prompt)],
                            config={"metadata": {"session_id": session_id, "operation": "condense_summary"}}
                        )
                        span.set_attribute("condensed_length", len(condensed.content))
                else:
                    condensed = summarization_model.invoke(
                        [HumanMessage(content=condense_prompt)],
                        config={"metadata": {"session_id": session_id, "operation": "condense_summary"}}
                    )
            return condensed.content[:MAX_SUMMARY_LENGTH]

        return summary_response.content

    def _build_context_window(
        self, session: Session, request: ChatRequest
    ) -> list[BaseMessage]:
        """Build context window: [SystemMessage(summary)] + recent_messages.

        Args:
            session: Current session
            request: Chat request

        Returns:
            List of messages to send to model
        """
        context = []

        # Add summary as SystemMessage if it exists
        if session.conversation_summary:
            summary_message = SystemMessage(
                content=f"Conversation Summary (covering {session.summary_message_count} earlier messages):\n\n{session.conversation_summary}"
            )
            context.append(summary_message)

        # Get recent message count
        keep_recent = request.memory_keep_recent or self.config.memory_keep_recent_count

        # Add recent messages (last N messages, excluding any old SystemMessages)
        real_messages = [m for m in session.messages if not isinstance(m, SystemMessage)]
        recent_messages = (
            real_messages[-keep_recent:] if len(real_messages) > keep_recent else real_messages
        )

        context.extend(recent_messages)

        return context

    def _format_messages_for_summary(self, messages: list[BaseMessage]) -> str:
        """Format messages for summary prompt.

        Args:
            messages: Messages to format

        Returns:
            Formatted conversation string
        """
        formatted_lines = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = "User"
            elif isinstance(msg, AIMessage):
                role = "Assistant"
            elif isinstance(msg, SystemMessage):
                role = "System"
            else:
                role = "Unknown"

            formatted_lines.append(f"{role}: {msg.content}")

        return "\n\n".join(formatted_lines)

    def _create_fallback_summary(self, messages: list[BaseMessage]) -> str:
        """Create basic summary without LLM.

        Args:
            messages: Messages to summarize

        Returns:
            Simple text-based summary
        """
        user_msgs = [m for m in messages if isinstance(m, HumanMessage)]
        ai_msgs = [m for m in messages if isinstance(m, AIMessage)]

        first_topic = "N/A"
        if user_msgs and user_msgs[0].content:
            first_topic = user_msgs[0].content[:100]

        return (
            f"[Automatic Summary - {len(messages)} messages]\n"
            f"User sent {len(user_msgs)} messages. "
            f"Assistant sent {len(ai_msgs)} responses. "
            f"First topic: {first_topic}..."
        )
