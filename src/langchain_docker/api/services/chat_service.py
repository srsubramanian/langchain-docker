"""Chat orchestration service."""

import json
import logging
from typing import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from langchain_docker.api.schemas.chat import ChatRequest, ChatResponse, MessageSchema
from langchain_docker.api.services.memory_service import MemoryService
from langchain_docker.api.services.mcp_tool_service import MCPToolService
from langchain_docker.api.services.model_service import ModelService
from langchain_docker.api.services.session_service import SessionService
from langchain_docker.core.tracing import trace_operation

logger = logging.getLogger(__name__)


class ChatService:
    """Service for orchestrating chat interactions.

    Coordinates between session management, memory management, and model invocation.
    """

    def __init__(
        self,
        session_service: SessionService,
        model_service: ModelService,
        memory_service: MemoryService,
        mcp_tool_service: MCPToolService | None = None,
    ):
        """Initialize chat service.

        Args:
            session_service: Session management service
            model_service: Model caching service
            memory_service: Memory management service
            mcp_tool_service: Optional MCP tool service for tool integration
        """
        self.session_service = session_service
        self.model_service = model_service
        self.memory_service = memory_service
        self.mcp_tool_service = mcp_tool_service

    def _parse_data_uri(self, uri: str) -> tuple[str, str]:
        """Parse data URI into mime type and base64 data.

        Args:
            uri: Data URI (e.g., 'data:image/png;base64,iVBORw0KGgo...')

        Returns:
            Tuple of (mime_type, base64_data)
        """
        # data:image/png;base64,iVBORw0KGgo...
        header, data = uri.split(",", 1)
        mime_type = header.split(":")[1].split(";")[0]
        return mime_type, data

    def _build_user_message(
        self, text: str, images: list[str] | None, provider: str
    ) -> HumanMessage:
        """Build a HumanMessage with optional image content.

        Args:
            text: Text message content
            images: Optional list of base64 data URIs
            provider: Model provider (for format-specific handling)

        Returns:
            HumanMessage with text and/or image content
        """
        if not images:
            return HumanMessage(content=text)

        # Build multimodal content blocks
        content: list[dict] = [{"type": "text", "text": text}]

        for image_uri in images:
            if provider == "anthropic":
                # Anthropic format: base64 with source
                mime_type, data = self._parse_data_uri(image_uri)
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": data
                    }
                })
            else:
                # OpenAI/Google/Bedrock format: image_url
                content.append({
                    "type": "image_url",
                    "image_url": {"url": image_uri}
                })

        return HumanMessage(content=content)

    def process_message(self, request: ChatRequest, user_id: str = "default") -> ChatResponse:
        """Process a chat message (non-streaming).

        Args:
            request: Chat request
            user_id: User ID for session scoping

        Returns:
            Chat response with AI message
        """
        # Get or create session (scoped to user)
        session = self.session_service.get_or_create(request.session_id, user_id=user_id)

        # Add user message to session (with optional images)
        user_message = self._build_user_message(
            request.message, request.images, request.provider
        )
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

        # Invoke model with optimized context window and enhanced tracing
        # trace_operation provides: session_id, user_id, metadata, and tags for Phoenix filtering
        with trace_operation(
            session_id=session.session_id,
            user_id=user_id,
            operation="chat",
            metadata={
                "provider": request.provider,
                "model": request.model or self.model_service._get_default_model(request.provider),
                "temperature": request.temperature,
                "message_count": len(context_messages),
            },
            tags=["chat", "non-streaming", request.provider],
        ):
            ai_response = model.invoke(
                context_messages,
                config={"metadata": {"session_id": session.session_id, "user_id": user_id}}
            )

        # Add AI response to session
        session.messages.append(ai_response)

        # Save session (required for Redis persistence)
        self.session_service.save(session)

        # Update session timestamp
        self.session_service.update_timestamp(session.session_id)

        # Convert to response schema (with memory metadata)
        return ChatResponse(
            session_id=session.session_id,
            message=MessageSchema.from_langchain(ai_response),
            conversation_length=len(session.messages),
            memory_metadata=memory_metadata,  # NEW
        )

    async def stream_message(self, request: ChatRequest, user_id: str = "default") -> AsyncGenerator[dict, None]:
        """Process a chat message with streaming.

        Args:
            request: Chat request
            user_id: User ID for session scoping

        Yields:
            Server-Sent Event dicts with event and data keys
        """
        # Get or create session (scoped to user)
        session = self.session_service.get_or_create(request.session_id, user_id=user_id)

        # Add user message to session (with optional images)
        user_message = self._build_user_message(
            request.message, request.images, request.provider
        )
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

        # Get MCP tools if specified
        mcp_tools = []
        tools_by_name = {}
        if request.mcp_servers and self.mcp_tool_service:
            try:
                mcp_tools = await self.mcp_tool_service.get_langchain_tools(
                    request.mcp_servers
                )
                tools_by_name = {tool.name: tool for tool in mcp_tools}
                logger.info(f"Loaded {len(mcp_tools)} MCP tools for chat")
            except Exception as e:
                logger.error(f"Failed to load MCP tools: {e}")

        # Bind tools to model if available
        if mcp_tools:
            model = model.bind_tools(mcp_tools)

        # Send start event (with memory info and tool count)
        yield {
            "event": "start",
            "data": json.dumps({
                "session_id": session.session_id,
                "model": request.model or self.model_service._get_default_model(request.provider),
                "provider": request.provider,
                "memory_metadata": memory_metadata.model_dump(mode='json'),
                "mcp_tools_count": len(mcp_tools),
            }),
        }

        # Helper to safely parse tool args (handles empty strings)
        def parse_args(args):
            if isinstance(args, str):
                if not args or args.strip() == "":
                    return {}
                return json.loads(args)
            return args if args else {}

        # Stream response tokens with enhanced tracing
        # trace_operation provides: session_id, user_id, metadata, and tags for Phoenix filtering
        full_content = ""
        tool_calls = []
        try:
            with trace_operation(
                session_id=session.session_id,
                user_id=user_id,
                operation="chat_stream",
                metadata={
                    "provider": request.provider,
                    "model": request.model or self.model_service._get_default_model(request.provider),
                    "temperature": request.temperature,
                    "message_count": len(context_messages),
                    "mcp_tools_count": len(mcp_tools),
                },
                tags=["chat", "streaming", request.provider] + (["mcp"] if mcp_tools else []),
            ):
                # Agentic loop: handle tool calls and continue generating
                max_iterations = 10  # Prevent infinite loops
                iteration = 0
                messages = list(context_messages)

                while iteration < max_iterations:
                    iteration += 1
                    full_content = ""
                    tool_calls = []

                    # Stream model response
                    for chunk in model.stream(
                        messages,
                        config={"metadata": {"session_id": session.session_id, "user_id": user_id}}
                    ):
                        # Accumulate content
                        if chunk.content:
                            content = chunk.content
                            if isinstance(content, list):
                                content = "".join(
                                    c.get("text", "") if isinstance(c, dict) else str(c)
                                    for c in content
                                )
                            full_content += content
                            yield {
                                "event": "token",
                                "data": json.dumps({"content": content}),
                            }

                        # Accumulate tool calls
                        if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                            for tc_chunk in chunk.tool_call_chunks:
                                # Find or create tool call entry
                                tc_id = tc_chunk.get("id") or tc_chunk.get("index", 0)
                                existing = next(
                                    (tc for tc in tool_calls if tc.get("id") == tc_id),
                                    None
                                )
                                if existing:
                                    # Append to existing tool call
                                    if tc_chunk.get("args"):
                                        existing["args"] = existing.get("args", "") + tc_chunk["args"]
                                else:
                                    tool_calls.append({
                                        "id": tc_id,
                                        "name": tc_chunk.get("name", ""),
                                        "args": tc_chunk.get("args", ""),
                                    })

                    # If no tool calls, we're done
                    if not tool_calls or not mcp_tools:
                        break

                    # Process tool calls
                    ai_message = AIMessage(
                        content=full_content,
                        tool_calls=[
                            {
                                "id": tc["id"],
                                "name": tc["name"],
                                "args": parse_args(tc["args"]),
                            }
                            for tc in tool_calls
                            if tc.get("name")
                        ]
                    )
                    messages.append(ai_message)

                    # Execute each tool call
                    for tc in tool_calls:
                        if not tc.get("name"):
                            continue

                        # Emit tool_call event
                        yield {
                            "event": "tool_call",
                            "data": json.dumps({
                                "tool_name": tc["name"],
                                "tool_id": tc["id"],
                                "arguments": tc["args"],
                            }),
                        }

                        # Execute the tool
                        tool_result = ""
                        try:
                            tool = tools_by_name.get(tc["name"])
                            if tool:
                                args = parse_args(tc["args"])
                                if tool.coroutine:
                                    tool_result = await tool.coroutine(**args)
                                else:
                                    tool_result = tool.func(**args)
                            else:
                                tool_result = f"Error: Tool '{tc['name']}' not found"
                        except Exception as e:
                            tool_result = f"Error executing tool: {e}"
                            logger.error(f"Tool execution error: {e}")

                        # Emit tool_result event
                        yield {
                            "event": "tool_result",
                            "data": json.dumps({
                                "tool_name": tc["name"],
                                "tool_id": tc["id"],
                                "result": str(tool_result)[:1000],  # Limit result size
                            }),
                        }

                        # Add tool result to messages
                        messages.append(ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tc["id"],
                        ))

            # Create final AI message
            ai_message = AIMessage(content=full_content)
            session.messages.append(ai_message)

            # Save session (required for Redis persistence)
            self.session_service.save(session)

            # Update session timestamp
            self.session_service.update_timestamp(session.session_id)

            # Send done event (with memory metadata)
            yield {
                "event": "done",
                "data": json.dumps({
                    "session_id": session.session_id,
                    "conversation_length": len(session.messages),
                    "message": MessageSchema.from_langchain(ai_message).model_dump(mode='json'),
                    "memory_metadata": memory_metadata.model_dump(mode='json'),
                }),
            }

        except Exception as e:
            logger.error(f"Stream error: {e}")
            # Send error event
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
