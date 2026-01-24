"""Chat orchestration service."""

import json
import logging
from typing import AsyncGenerator, Optional

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from langchain_docker.api.schemas.chat import ChatRequest, ChatResponse, MessageSchema
from langchain_docker.api.services.approval_service import ApprovalService, ApprovalConfig
from langchain_docker.api.services.knowledge_base_service import KnowledgeBaseService
from langchain_docker.api.services.memory_service import MemoryService
from langchain_docker.api.services.mcp_tool_service import MCPToolService
from langchain_docker.api.services.model_service import ModelService
from langchain_docker.api.services.session_service import SessionService
from langchain_docker.core.tracing import trace_operation

logger = logging.getLogger(__name__)


class ChatService:
    """Service for orchestrating chat interactions.

    Coordinates between session management, memory management, and model invocation.
    Supports Human-in-the-Loop (HITL) approval for tools that require it.
    """

    def __init__(
        self,
        session_service: SessionService,
        model_service: ModelService,
        memory_service: MemoryService,
        mcp_tool_service: MCPToolService | None = None,
        approval_service: ApprovalService | None = None,
        kb_service: KnowledgeBaseService | None = None,
    ):
        """Initialize chat service.

        Args:
            session_service: Session management service
            model_service: Model caching service
            memory_service: Memory management service
            mcp_tool_service: Optional MCP tool service for tool integration
            approval_service: Optional approval service for HITL tools
            kb_service: Optional knowledge base service for RAG
        """
        self.session_service = session_service
        self.model_service = model_service
        self.memory_service = memory_service
        self.mcp_tool_service = mcp_tool_service
        self.approval_service = approval_service
        self.kb_service = kb_service
        # Map of tool names to their HITL configs
        self._hitl_tools: dict[str, ApprovalConfig] = {}

    def register_hitl_tool(self, tool_name: str, config: ApprovalConfig) -> None:
        """Register a tool that requires HITL approval.

        Args:
            tool_name: Name of the tool
            config: Approval configuration for the tool
        """
        self._hitl_tools[tool_name] = config
        logger.info(f"Registered HITL tool: {tool_name}")

    def unregister_hitl_tool(self, tool_name: str) -> None:
        """Unregister a HITL tool.

        Args:
            tool_name: Name of the tool to unregister
        """
        self._hitl_tools.pop(tool_name, None)

    def is_hitl_tool(self, tool_name: str) -> bool:
        """Check if a tool requires HITL approval.

        Args:
            tool_name: Name of the tool

        Returns:
            True if the tool requires approval
        """
        return tool_name in self._hitl_tools

    def _get_rag_context(self, request: ChatRequest) -> str | None:
        """Get RAG context from knowledge base if enabled.

        Args:
            request: Chat request with RAG settings

        Returns:
            RAG context string or None if RAG is disabled or unavailable
        """
        if not request.enable_rag:
            return None

        if not self.kb_service or not self.kb_service.is_available:
            logger.warning("RAG enabled but knowledge base is not available")
            return None

        try:
            context = self.kb_service.get_context_for_query(
                query=request.message,
                top_k=request.rag_top_k,
                min_score=request.rag_min_score,
                collection=request.rag_collection,
            )
            if context:
                logger.info(f"RAG: Retrieved context for query (top_k={request.rag_top_k})")
            return context if context else None
        except Exception as e:
            logger.error(f"Failed to get RAG context: {e}")
            return None

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

    async def _stream_with_anthropic_caching(
        self,
        request: ChatRequest,
        session,
        context_messages: list,
        memory_metadata,
        mcp_tools: list,
        mcp_session_ctx,
        user_id: str,
    ) -> AsyncGenerator[dict, None]:
        """Stream with Anthropic prompt caching middleware.

        Uses create_agent with AnthropicPromptCachingMiddleware to cache
        tool definitions and system prompts, reducing ITPM usage.

        Args:
            request: Chat request
            session: Session object
            context_messages: Processed conversation messages
            memory_metadata: Memory metadata from processing
            mcp_tools: List of MCP tools
            mcp_session_ctx: MCP session context manager
            user_id: User ID for session scoping

        Yields:
            Server-Sent Event dicts with event and data keys
        """
        try:
            # Create Anthropic model with caching support
            model_name = request.model or "claude-sonnet-4-20250514"
            anthropic_model = ChatAnthropic(
                model=model_name,
                temperature=request.temperature,
            )

            # Extract system prompt from context messages if present
            system_prompt = None
            user_messages = []
            for msg in context_messages:
                if isinstance(msg, SystemMessage):
                    system_prompt = msg.content if isinstance(msg.content, str) else str(msg.content)
                else:
                    user_messages.append(msg)

            # Create agent with prompt caching middleware
            # This caches tool definitions and system prompt for 5 minutes
            agent = create_agent(
                model=anthropic_model,
                tools=mcp_tools if mcp_tools else None,
                system_prompt=system_prompt,
                middleware=[AnthropicPromptCachingMiddleware(ttl="5m")],
            )

            # Send start event
            yield {
                "event": "start",
                "data": json.dumps({
                    "session_id": session.session_id,
                    "model": model_name,
                    "provider": "anthropic",
                    "memory_metadata": memory_metadata.model_dump(mode='json'),
                    "mcp_tools_count": len(mcp_tools),
                    "prompt_caching": True,
                }),
            }

            # Stream with the agent using astream_events
            accumulated_content = ""
            final_messages = []

            with trace_operation(
                session_id=session.session_id,
                user_id=user_id,
                operation="chat_stream_anthropic_cached",
                metadata={
                    "provider": "anthropic",
                    "model": model_name,
                    "temperature": request.temperature,
                    "message_count": len(context_messages),
                    "mcp_tools_count": len(mcp_tools),
                    "prompt_caching": True,
                },
                tags=["chat", "streaming", "anthropic", "prompt_caching"] + (["mcp"] if mcp_tools else []),
            ):
                async for event in agent.astream_events(
                    {"messages": user_messages},
                    config={
                        "configurable": {"thread_id": session.session_id},
                        "metadata": {"session_id": session.session_id, "user_id": user_id},
                    },
                    version="v2",
                ):
                    kind = event.get("event", "")
                    data = event.get("data", {})

                    # Tool call started
                    if kind == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        tool_input = data.get("input", {})
                        try:
                            if isinstance(tool_input, dict):
                                safe_input = {
                                    k: v for k, v in tool_input.items()
                                    if isinstance(v, (str, int, float, bool, list, dict, type(None)))
                                }
                                args_str = json.dumps(safe_input)
                            else:
                                args_str = str(tool_input)
                        except (TypeError, ValueError):
                            args_str = str(tool_input)
                        yield {
                            "event": "tool_call",
                            "data": json.dumps({
                                "tool_name": tool_name,
                                "tool_id": event.get("run_id", ""),
                                "arguments": args_str,
                            }),
                        }

                    # Tool call completed
                    elif kind == "on_tool_end":
                        tool_name = event.get("name", "unknown")
                        output = data.get("output", "")
                        output_str = str(output)[:1000] if output else ""
                        yield {
                            "event": "tool_result",
                            "data": json.dumps({
                                "tool_name": tool_name,
                                "tool_id": event.get("run_id", ""),
                                "result": output_str,
                            }),
                        }

                    # Streaming tokens from LLM
                    elif kind == "on_chat_model_stream":
                        chunk = data.get("chunk")
                        if chunk and hasattr(chunk, 'content') and chunk.content:
                            content = chunk.content
                            if isinstance(content, str):
                                accumulated_content += content
                                yield {"event": "token", "data": json.dumps({"content": content})}
                            elif isinstance(content, list):
                                text_content = "".join(
                                    c.get("text", "") if isinstance(c, dict) else str(c)
                                    for c in content
                                )
                                if text_content:
                                    accumulated_content += text_content
                                    yield {"event": "token", "data": json.dumps({"content": text_content})}

                    # Chain/graph end - capture final messages
                    elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                        output = data.get("output", {})
                        if isinstance(output, dict) and "messages" in output:
                            final_messages = output["messages"]

            # Update session with final messages or accumulated content
            if final_messages:
                session.messages = final_messages
            else:
                session.messages.append(AIMessage(content=accumulated_content))

            # Save session
            self.session_service.save(session)
            self.session_service.update_timestamp(session.session_id)

            # Extract response for done event
            response_content = accumulated_content
            if final_messages:
                for msg in reversed(final_messages):
                    if isinstance(msg, AIMessage) and msg.content:
                        content = msg.content
                        if isinstance(content, str):
                            response_content = content
                        elif isinstance(content, list):
                            # Handle Anthropic's content blocks format
                            text_parts = []
                            for block in content:
                                if isinstance(block, dict) and "text" in block:
                                    text_parts.append(block["text"])
                                elif isinstance(block, str):
                                    text_parts.append(block)
                            response_content = "".join(text_parts) if text_parts else str(content)
                        else:
                            response_content = str(content)
                        break

            # Send done event
            yield {
                "event": "done",
                "data": json.dumps({
                    "session_id": session.session_id,
                    "conversation_length": len(session.messages),
                    "message": MessageSchema.from_langchain(
                        AIMessage(content=response_content)
                    ).model_dump(mode='json'),
                    "memory_metadata": memory_metadata.model_dump(mode='json'),
                }),
            }

        except Exception as e:
            logger.error(f"Anthropic cached stream error: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

        finally:
            # Clean up MCP session context
            if mcp_session_ctx:
                try:
                    await mcp_session_ctx.__aexit__(None, None, None)
                    logger.info("Closed MCP persistent sessions")
                except Exception as e:
                    logger.error(f"Error closing MCP sessions: {e}")

    async def _stream_with_bedrock_caching(
        self,
        request: ChatRequest,
        session,
        context_messages: list,
        memory_metadata,
        mcp_tools: list,
        mcp_session_ctx,
        user_id: str,
    ) -> AsyncGenerator[dict, None]:
        """Stream with Bedrock prompt caching using cachePoint.

        Uses ChatBedrockConverse with cachePoint markers to cache
        tool definitions and system prompts, reducing ITPM usage.

        Bedrock caching requires:
        - botocore >= 1.37.25
        - Content > 1024 tokens (2048 for Haiku)
        - Supported models: Claude 3.5 Sonnet V2+, Claude 3.7 Sonnet, Claude 4 Sonnet

        Args:
            request: Chat request
            session: Session object
            context_messages: Processed conversation messages
            memory_metadata: Memory metadata from processing
            mcp_tools: List of MCP tools
            mcp_session_ctx: MCP session context manager
            user_id: User ID for session scoping

        Yields:
            Server-Sent Event dicts with event and data keys
        """
        from langchain_docker.core.models import create_bedrock_client
        from langchain_docker.core.config import get_bedrock_models

        try:
            # Get model name - use request model or first configured Bedrock model
            model_name = request.model
            if not model_name:
                available_models = get_bedrock_models()
                model_name = available_models[0] if available_models else "anthropic.claude-3-5-sonnet-20241022-v2:0"

            # Create Bedrock model
            bedrock_model = ChatBedrockConverse(
                model=model_name,
                temperature=request.temperature,
                client=create_bedrock_client(),
            )

            # Extract system prompt from context messages
            system_prompt = None
            user_messages = []
            for msg in context_messages:
                if isinstance(msg, SystemMessage):
                    system_prompt = msg.content if isinstance(msg.content, str) else str(msg.content)
                else:
                    user_messages.append(msg)

            # Build system message with cache point for tool definitions
            # This caches the system prompt + tool definitions
            system_content = []
            if system_prompt:
                system_content.append({"type": "text", "text": system_prompt})

            # Add tool definitions to system prompt for caching
            if mcp_tools:
                tool_definitions = []
                for tool in mcp_tools:
                    tool_def = {
                        "name": tool.name,
                        "description": tool.description or "",
                    }
                    if hasattr(tool, 'args_schema') and tool.args_schema:
                        # Handle both Pydantic model classes and dict schemas
                        args_schema = tool.args_schema
                        if hasattr(args_schema, 'schema'):
                            tool_def["parameters"] = args_schema.schema()
                        elif isinstance(args_schema, dict):
                            tool_def["parameters"] = args_schema
                    tool_definitions.append(tool_def)

                tools_text = f"\n\nAvailable tools:\n{json.dumps(tool_definitions, indent=2)}"
                system_content.append({"type": "text", "text": tools_text})

            # Add cache point after system content (caches everything before it)
            if system_content:
                system_content.append({"cachePoint": {"type": "default"}})

            # Create system message with cache point
            cached_system_msg = SystemMessage(content=system_content) if system_content else None

            # Build final messages list
            final_messages = []
            if cached_system_msg:
                final_messages.append(cached_system_msg)
            final_messages.extend(user_messages)

            # Send start event
            yield {
                "event": "start",
                "data": json.dumps({
                    "session_id": session.session_id,
                    "model": model_name,
                    "provider": "bedrock",
                    "memory_metadata": memory_metadata.model_dump(mode='json'),
                    "mcp_tools_count": len(mcp_tools),
                    "prompt_caching": True,
                }),
            }

            # Bind tools to model
            if mcp_tools:
                bedrock_model = bedrock_model.bind_tools(mcp_tools)

            # Stream with the model
            accumulated_content = ""
            tool_calls_pending = []

            with trace_operation(
                session_id=session.session_id,
                user_id=user_id,
                operation="chat_stream_bedrock_cached",
                metadata={
                    "provider": "bedrock",
                    "model": model_name,
                    "temperature": request.temperature,
                    "message_count": len(final_messages),
                    "mcp_tools_count": len(mcp_tools),
                    "prompt_caching": True,
                },
                tags=["chat", "streaming", "bedrock", "prompt_caching"] + (["mcp"] if mcp_tools else []),
            ):
                # Use astream for streaming responses
                async for chunk in bedrock_model.astream(final_messages):
                    # Handle content chunks
                    if chunk.content:
                        content = chunk.content
                        if isinstance(content, str):
                            accumulated_content += content
                            yield {"event": "token", "data": json.dumps({"content": content})}
                        elif isinstance(content, list):
                            text_content = "".join(
                                c.get("text", "") if isinstance(c, dict) else str(c)
                                for c in content
                                if isinstance(c, dict) and c.get("type") == "text" or isinstance(c, str)
                            )
                            if text_content:
                                accumulated_content += text_content
                                yield {"event": "token", "data": json.dumps({"content": text_content})}

                    # Handle tool calls
                    if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                        for tool_call in chunk.tool_calls:
                            tool_name = tool_call.get("name", "unknown")
                            tool_args = tool_call.get("args", {})
                            tool_id = tool_call.get("id", "")

                            yield {
                                "event": "tool_call",
                                "data": json.dumps({
                                    "tool_name": tool_name,
                                    "tool_id": tool_id,
                                    "arguments": json.dumps(tool_args) if isinstance(tool_args, dict) else str(tool_args),
                                }),
                            }
                            tool_calls_pending.append(tool_call)

                # Execute pending tool calls
                if tool_calls_pending and mcp_tools:
                    tools_by_name = {tool.name: tool for tool in mcp_tools}
                    for tool_call in tool_calls_pending:
                        tool_name = tool_call.get("name", "")
                        tool_args = tool_call.get("args", {})
                        tool_id = tool_call.get("id", "")

                        if tool_name in tools_by_name:
                            try:
                                tool = tools_by_name[tool_name]
                                result = await tool.ainvoke(tool_args)
                                result_str = str(result)[:1000] if result else ""
                                yield {
                                    "event": "tool_result",
                                    "data": json.dumps({
                                        "tool_name": tool_name,
                                        "tool_id": tool_id,
                                        "result": result_str,
                                    }),
                                }

                                # Add tool message and continue conversation
                                final_messages.append(AIMessage(content="", tool_calls=[tool_call]))
                                final_messages.append(ToolMessage(content=result_str, tool_call_id=tool_id))

                            except Exception as e:
                                logger.error(f"Tool execution error: {e}")
                                yield {
                                    "event": "tool_result",
                                    "data": json.dumps({
                                        "tool_name": tool_name,
                                        "tool_id": tool_id,
                                        "result": f"Error: {str(e)}",
                                    }),
                                }

                    # Get final response after tool execution
                    async for chunk in bedrock_model.astream(final_messages):
                        if chunk.content:
                            content = chunk.content
                            if isinstance(content, str):
                                accumulated_content += content
                                yield {"event": "token", "data": json.dumps({"content": content})}
                            elif isinstance(content, list):
                                text_content = "".join(
                                    c.get("text", "") if isinstance(c, dict) else str(c)
                                    for c in content
                                    if isinstance(c, dict) and c.get("type") == "text" or isinstance(c, str)
                                )
                                if text_content:
                                    accumulated_content += text_content
                                    yield {"event": "token", "data": json.dumps({"content": text_content})}

            # Update session with response
            session.messages.append(AIMessage(content=accumulated_content))
            self.session_service.save(session)
            self.session_service.update_timestamp(session.session_id)

            # Send done event
            yield {
                "event": "done",
                "data": json.dumps({
                    "session_id": session.session_id,
                    "conversation_length": len(session.messages),
                    "message": MessageSchema.from_langchain(
                        AIMessage(content=accumulated_content)
                    ).model_dump(mode='json'),
                    "memory_metadata": memory_metadata.model_dump(mode='json'),
                }),
            }

        except Exception as e:
            logger.error(f"Bedrock cached stream error: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

        finally:
            # Clean up MCP session context
            if mcp_session_ctx:
                try:
                    await mcp_session_ctx.__aexit__(None, None, None)
                    logger.info("Closed MCP persistent sessions")
                except Exception as e:
                    logger.error(f"Error closing MCP sessions: {e}")

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

        # Get RAG context if enabled
        rag_context = self._get_rag_context(request)

        # Process conversation memory (with optional RAG context)
        context_messages, memory_metadata = self.memory_service.process_conversation(
            session, request, rag_context=rag_context
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

        # Get RAG context if enabled
        rag_context = self._get_rag_context(request)

        # Process conversation memory (with optional RAG context)
        context_messages, memory_metadata = self.memory_service.process_conversation(
            session, request, rag_context=rag_context
        )

        # Get model from cache
        model = self.model_service.get_or_create(
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        # Helper to safely parse tool args (handles empty strings)
        def parse_args(args):
            if isinstance(args, str):
                if not args or args.strip() == "":
                    return {}
                return json.loads(args)
            return args if args else {}

        # Get MCP tools if specified - use persistent sessions for stateful servers
        mcp_tools = []
        tools_by_name = {}
        mcp_session_ctx = None

        # Check if we need MCP tools with persistent sessions
        if request.mcp_servers and self.mcp_tool_service:
            try:
                # Use the context manager to get tools with persistent sessions
                # This keeps MCP subprocesses (like chrome-devtools) alive during execution
                mcp_session_ctx = self.mcp_tool_service.get_tools_with_session(
                    request.mcp_servers
                )
                mcp_tools = await mcp_session_ctx.__aenter__()
                tools_by_name = {tool.name: tool for tool in mcp_tools}
                logger.info(f"Loaded {len(mcp_tools)} MCP tools with persistent sessions")
            except Exception as e:
                logger.error(f"Failed to load MCP tools: {e}")
                mcp_session_ctx = None

        # Use Anthropic prompt caching when available for better ITPM efficiency
        # This caches tool definitions and system prompts, reducing token usage by ~80%
        if request.provider == "anthropic" and mcp_tools:
            logger.info(f"Using Anthropic prompt caching middleware for {len(mcp_tools)} tools")
            async for event in self._stream_with_anthropic_caching(
                request=request,
                session=session,
                context_messages=context_messages,
                memory_metadata=memory_metadata,
                mcp_tools=mcp_tools,
                mcp_session_ctx=mcp_session_ctx,
                user_id=user_id,
            ):
                yield event
            return  # Exit early - Anthropic method handles everything

        # Use Bedrock prompt caching when available for better ITPM efficiency
        # This caches tool definitions and system prompts using cachePoint markers
        if request.provider == "bedrock" and mcp_tools:
            logger.info(f"Using Bedrock prompt caching for {len(mcp_tools)} tools")
            async for event in self._stream_with_bedrock_caching(
                request=request,
                session=session,
                context_messages=context_messages,
                memory_metadata=memory_metadata,
                mcp_tools=mcp_tools,
                mcp_session_ctx=mcp_session_ctx,
                user_id=user_id,
            ):
                yield event
            return  # Exit early - Bedrock method handles everything

        try:
            # Bind tools to model if available (non-cached path)
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

            # Stream response tokens with enhanced tracing
            # trace_operation provides: session_id, user_id, metadata, and tags for Phoenix filtering
            full_content = ""
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

                        # Stream model response and accumulate chunks
                        # LangChain's AIMessageChunk supports + operator for proper merging
                        # including tool_call_chunks -> tool_calls accumulation
                        gathered = None
                        for chunk in model.stream(
                            messages,
                            config={"metadata": {"session_id": session.session_id, "user_id": user_id}}
                        ):
                            # Accumulate chunks using LangChain's built-in merging
                            gathered = chunk if gathered is None else gathered + chunk

                            # Stream content tokens to client
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

                        # Extract tool calls from accumulated message
                        # LangChain automatically parses tool_call_chunks into tool_calls
                        tool_calls = gathered.tool_calls if gathered and hasattr(gathered, "tool_calls") else []

                        # If no tool calls, we're done
                        if not tool_calls or not mcp_tools:
                            break

                        # Build AI message with accumulated tool calls
                        ai_message = AIMessage(
                            content=full_content,
                            tool_calls=tool_calls
                        )
                        messages.append(ai_message)

                        # Execute each tool call
                        for tc in tool_calls:
                            if not tc.get("name"):
                                continue

                            tool_name = tc["name"]
                            tool_id = tc["id"]
                            # LangChain's accumulated tool_calls have args as dict
                            args = tc["args"] if isinstance(tc["args"], dict) else parse_args(tc["args"])
                            logger.info(f"Tool call '{tool_name}': args={args}")

                            # Emit tool_call event (serialize args for client)
                            yield {
                                "event": "tool_call",
                                "data": json.dumps({
                                    "tool_name": tool_name,
                                    "tool_id": tool_id,
                                    "arguments": json.dumps(args) if isinstance(args, dict) else args,
                                }),
                            }

                            # Check if this tool requires HITL approval
                            hitl_config = self._hitl_tools.get(tool_name)
                            if hitl_config and self.approval_service:
                                # Create approval request
                                approval = self.approval_service.create(
                                    tool_call_id=tool_id,
                                    session_id=session.session_id,
                                    thread_id=session.session_id,  # Use session as thread for simple case
                                    tool_name=tool_name,
                                    tool_args=args if hitl_config.show_args else {},
                                    config=hitl_config,
                                )

                                # Emit approval_request event
                                yield {
                                    "event": "approval_request",
                                    "data": json.dumps({
                                        "approval_id": approval.id,
                                        "tool_name": tool_name,
                                        "tool_id": tool_id,
                                        "message": hitl_config.message,
                                        "tool_args": args if hitl_config.show_args else None,
                                        "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                                        "config": {
                                            "show_args": hitl_config.show_args,
                                            "timeout_seconds": hitl_config.timeout_seconds,
                                            "require_reason_on_reject": hitl_config.require_reason_on_reject,
                                        },
                                    }),
                                }

                                # For now, return a pending message
                                # Full implementation would use LangGraph interrupt/resume
                                tool_result = (
                                    f"[APPROVAL REQUIRED] Action '{tool_name}' requires human approval. "
                                    f"Approval ID: {approval.id}. "
                                    "Waiting for user to approve or reject this action."
                                )
                                logger.info(f"HITL approval requested: {approval.id} for {tool_name}")
                            else:
                                # Execute the tool normally using standard LangChain interface
                                tool_result = ""
                                try:
                                    tool = tools_by_name.get(tool_name)
                                    if tool:
                                        # Use ainvoke() - the standard async interface for all LangChain tools
                                        tool_result = await tool.ainvoke(args)
                                    else:
                                        tool_result = f"Error: Tool '{tool_name}' not found"
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

        finally:
            # Clean up MCP session context (closes persistent sessions)
            if mcp_session_ctx:
                try:
                    await mcp_session_ctx.__aexit__(None, None, None)
                    logger.info("Closed MCP persistent sessions")
                except Exception as e:
                    logger.error(f"Error closing MCP sessions: {e}")
