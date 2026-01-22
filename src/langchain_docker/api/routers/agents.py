"""Multi-agent API endpoints.

Unified endpoint structure:
- GET  /agents                    - List all agents (custom + builtin)
- GET  /agents/{agent_id}         - Get agent details
- POST /agents                    - Create custom agent
- DELETE /agents/{agent_id}       - Delete custom agent
- POST /agents/{agent_id}/invoke  - Invoke any agent (non-streaming)
- POST /agents/{agent_id}/invoke/stream - Invoke any agent (streaming)
- DELETE /agents/{agent_id}/session - Clear agent session

- GET  /agents/tools              - List tool templates
- GET  /agents/tools/categories   - List tool categories

- GET  /workflows                 - List workflows
- POST /workflows                 - Create workflow
- POST /workflows/{id}/invoke     - Invoke workflow (non-streaming)
- POST /workflows/{id}/invoke/stream - Invoke workflow (streaming)
- DELETE /workflows/{id}          - Delete workflow
"""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from langchain_docker.api.dependencies import get_agent_service, get_current_user_id
from langchain_docker.api.schemas.agents import (
    AgentInfo,
    CustomAgentCreateRequest,
    CustomAgentCreateResponse,
    CustomAgentDeleteResponse,
    CustomAgentInfo,
    CustomAgentUpdateRequest,
    CustomAgentUpdateResponse,
    DirectInvokeRequest,
    DirectInvokeResponse,
    ScheduleInfo,
    ToolTemplateSchema,
    WorkflowCreateRequest,
    WorkflowCreateResponse,
    WorkflowDeleteResponse,
    WorkflowInfo,
    WorkflowInvokeRequest,
    WorkflowInvokeResponse,
)
from langchain_docker.api.services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


# =============================================================================
# UNIFIED AGENT ENDPOINTS
# These endpoints work with both custom and built-in agents
# =============================================================================


@router.get("", response_model=list[dict])
def list_all_agents(
    agent_type: str = Query(None, description="Filter by type: 'custom' or 'builtin'"),
    agent_service: AgentService = Depends(get_agent_service),
):
    """List all agents (both custom and built-in).

    Args:
        agent_type: Optional filter for agent type ('custom' or 'builtin')

    Returns:
        List of all agents with unified schema
    """
    agents = agent_service.list_all_agents()

    if agent_type:
        agents = [a for a in agents if a.get("type") == agent_type]

    return agents


# =============================================================================
# STATIC PATH ENDPOINTS (must come before /{agent_id} to avoid route conflicts)
# =============================================================================


@router.get("/tools", response_model=list[ToolTemplateSchema])
def list_tool_templates(
    agent_service: AgentService = Depends(get_agent_service),
):
    """List all available tool templates.

    Returns tool templates with their configurable parameters.
    These can be used to build custom agents.

    Returns:
        List of tool templates
    """
    return agent_service.list_tool_templates()


@router.get("/tools/categories", response_model=list[str])
def list_tool_categories(
    agent_service: AgentService = Depends(get_agent_service),
):
    """List all tool categories.

    Returns:
        List of category names (math, weather, research, finance, etc.)
    """
    return agent_service.list_tool_categories()


@router.get("/builtin", response_model=list[AgentInfo])
def list_builtin_agents(
    agent_service: AgentService = Depends(get_agent_service),
):
    """List all available built-in agents.

    DEPRECATED: Use GET /agents?agent_type=builtin instead.

    Returns:
        List of built-in agent configurations
    """
    return agent_service.list_builtin_agents()


@router.get("/custom", response_model=list[CustomAgentInfo])
def list_custom_agents(
    agent_service: AgentService = Depends(get_agent_service),
):
    """List all custom agents created by users.

    DEPRECATED: Use GET /agents?agent_type=custom instead.

    Returns:
        List of custom agent information
    """
    return agent_service.list_custom_agents()


# =============================================================================
# PARAMETERIZED AGENT ENDPOINTS (must come after static paths)
# =============================================================================


@router.get("/{agent_id}")
def get_agent(
    agent_id: str,
    agent_service: AgentService = Depends(get_agent_service),
):
    """Get details of any agent (custom or built-in).

    Args:
        agent_id: Agent ID

    Returns:
        Agent information
    """
    try:
        agent_type, config, custom = agent_service._get_agent_info(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if agent_type == "custom":
        # Build detailed custom agent info
        schedule_info = None
        if custom.schedule:
            schedule_data = agent_service.get_agent_schedule(agent_id)
            schedule_info = {
                "enabled": custom.schedule.enabled,
                "cron_expression": custom.schedule.cron_expression,
                "trigger_prompt": custom.schedule.trigger_prompt,
                "timezone": custom.schedule.timezone,
                "next_run": schedule_data.get("next_run") if schedule_data else None,
            }

        return {
            "id": agent_id,
            "name": custom.name,
            "type": "custom",
            "tools": [tc["tool_id"] for tc in custom.tool_configs],
            "skills": custom.skill_ids or [],
            "description": custom.system_prompt[:100] + "..." if len(custom.system_prompt) > 100 else custom.system_prompt,
            "system_prompt": custom.system_prompt,
            "schedule": schedule_info,
            "created_at": custom.created_at.isoformat(),
            "provider": custom.provider,
            "model": custom.model,
            "temperature": custom.temperature,
        }
    else:
        # Built-in agent info
        if "tool_ids" in config:
            tool_names = config["tool_ids"]
        else:
            tool_names = [t.__name__ for t in config.get("tools", [])]

        return {
            "id": agent_id,
            "name": config["name"],
            "type": "builtin",
            "tools": tool_names,
            "description": config["prompt"][:100] + "..." if len(config["prompt"]) > 100 else config["prompt"],
            "system_prompt": config["prompt"],
        }


@router.post("", response_model=CustomAgentCreateResponse, status_code=201)
def create_agent(
    request: CustomAgentCreateRequest,
    agent_service: AgentService = Depends(get_agent_service),
):
    """Create a custom agent from tool selections and skills.

    Select tools from the registry and/or skills to include.
    Skills automatically add their context to the system prompt.
    Optionally configure a schedule for automated execution.

    Args:
        request: Custom agent configuration

    Returns:
        Created custom agent information
    """
    agent_id = request.agent_id or str(uuid.uuid4())

    try:
        tool_configs = [
            {"tool_id": t.tool_id, "config": t.config}
            for t in request.tools
        ]

        schedule_config = None
        if request.schedule:
            schedule_config = {
                "enabled": request.schedule.enabled,
                "cron_expression": request.schedule.cron_expression,
                "trigger_prompt": request.schedule.trigger_prompt,
                "timezone": request.schedule.timezone,
            }

        agent_service.create_custom_agent(
            agent_id=agent_id,
            name=request.name,
            system_prompt=request.system_prompt,
            tool_configs=tool_configs,
            skill_ids=request.skills,
            schedule_config=schedule_config,
            metadata=request.metadata,
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    message_parts = []
    if request.tools:
        message_parts.append(f"{len(request.tools)} tools")
    if request.skills:
        message_parts.append(f"{len(request.skills)} skills")
    if request.schedule and request.schedule.enabled:
        message_parts.append("scheduled")

    return CustomAgentCreateResponse(
        agent_id=agent_id,
        name=request.name,
        tools=[t.tool_id for t in request.tools],
        schedule_enabled=request.schedule.enabled if request.schedule else False,
        message=f"Custom agent '{request.name}' created with {' and '.join(message_parts) if message_parts else 'default config'}",
    )


@router.put("/{agent_id}", response_model=CustomAgentUpdateResponse)
def update_agent(
    agent_id: str,
    request: CustomAgentUpdateRequest,
    agent_service: AgentService = Depends(get_agent_service),
):
    """Update a custom agent.

    Only provided fields are updated; others remain unchanged.
    This can be used to change the provider, model, temperature,
    tools, skills, or any other configuration.

    Note: Built-in agents cannot be updated.

    Args:
        agent_id: Agent ID to update
        request: Fields to update (all optional)

    Returns:
        Updated agent information
    """
    # Check if it's a built-in agent
    all_builtin = agent_service._get_all_builtin_agents()
    if agent_id in all_builtin:
        raise HTTPException(status_code=400, detail="Cannot update built-in agents")

    try:
        # Convert tool configs if provided
        tool_configs = None
        if request.tools is not None:
            tool_configs = [
                {"tool_id": t.tool_id, "config": t.config}
                for t in request.tools
            ]

        # Convert schedule config if provided
        schedule_config = None
        if request.schedule is not None:
            schedule_config = {
                "enabled": request.schedule.enabled,
                "cron_expression": request.schedule.cron_expression,
                "trigger_prompt": request.schedule.trigger_prompt,
                "timezone": request.schedule.timezone,
            }

        agent = agent_service.update_custom_agent(
            agent_id=agent_id,
            name=request.name,
            system_prompt=request.system_prompt,
            tool_configs=tool_configs,
            skill_ids=request.skills,
            schedule_config=schedule_config,
            metadata=request.metadata,
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
        )

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    return CustomAgentUpdateResponse(
        agent_id=agent.id,
        name=agent.name,
        tools=[tc["tool_id"] for tc in agent.tool_configs],
        skills=agent.skill_ids or [],
        provider=agent.provider,
        model=agent.model,
        temperature=agent.temperature,
        message=f"Custom agent '{agent.name}' updated successfully",
    )


@router.delete("/{agent_id}", response_model=CustomAgentDeleteResponse)
def delete_agent(
    agent_id: str,
    agent_service: AgentService = Depends(get_agent_service),
):
    """Delete a custom agent.

    Note: Built-in agents cannot be deleted.

    Args:
        agent_id: Agent ID to delete

    Returns:
        Deletion status
    """
    # Check if it's a built-in agent
    all_builtin = agent_service._get_all_builtin_agents()
    if agent_id in all_builtin:
        raise HTTPException(status_code=400, detail="Cannot delete built-in agents")

    deleted = agent_service.delete_custom_agent(agent_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return CustomAgentDeleteResponse(
        agent_id=agent_id,
        deleted=True,
    )


@router.post("/{agent_id}/invoke", response_model=DirectInvokeResponse)
def invoke_agent(
    agent_id: str,
    request: DirectInvokeRequest,
    user_id: str = Depends(get_current_user_id),
    agent_service: AgentService = Depends(get_agent_service),
):
    """Invoke any agent (custom or built-in) directly without supervisor.

    This endpoint allows direct interaction with any agent, enabling
    human-in-the-loop scenarios where the agent can ask for confirmation
    and the user can respond.

    Args:
        agent_id: Agent ID (custom or built-in)
        request: Message to process with memory options and optional images

    Returns:
        Agent response with session ID and memory metadata
    """
    session_id = request.session_id or f"{user_id}:agent:{agent_id}"

    try:
        result = agent_service.invoke_agent(
            agent_id=agent_id,
            message=request.message,
            images=request.images,
            session_id=session_id,
            user_id=user_id,
            enable_memory=request.enable_memory,
            memory_trigger_count=request.memory_trigger_count,
            memory_keep_recent=request.memory_keep_recent,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return DirectInvokeResponse(**result)


@router.post("/{agent_id}/invoke/stream")
async def invoke_agent_stream(
    agent_id: str,
    request: DirectInvokeRequest,
    user_id: str = Depends(get_current_user_id),
    agent_service: AgentService = Depends(get_agent_service),
):
    """Stream responses from any agent (custom or built-in) directly.

    This endpoint streams SSE events for tool calls, tool results, and tokens.
    Use this to show real-time skill loading and agent responses.

    Events:
        - start: Initial event with session info
        - tool_call: When a tool (including skill loaders) is called
        - tool_result: Result of a tool call
        - token: Streaming text token
        - done: Final event with complete response
        - error: If an error occurs

    Args:
        agent_id: Agent ID (custom or built-in)
        request: Message to process with memory options and optional images

    Returns:
        SSE stream of events
    """
    session_id = request.session_id or f"{user_id}:agent:{agent_id}"

    async def event_generator():
        async for event in agent_service.stream_agent(
            agent_id=agent_id,
            message=request.message,
            images=request.images,
            session_id=session_id,
            user_id=user_id,
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
            enable_memory=request.enable_memory,
            memory_trigger_count=request.memory_trigger_count,
            memory_keep_recent=request.memory_keep_recent,
            mcp_servers=request.mcp_servers,
        ):
            yield {
                "event": event.get("event", "message"),
                "data": event.get("data", "{}"),
            }

    return EventSourceResponse(event_generator())


@router.delete("/{agent_id}/session", status_code=204)
def clear_agent_session(
    agent_id: str,
    session_id: str = None,
    user_id: str = Depends(get_current_user_id),
    agent_service: AgentService = Depends(get_agent_service),
):
    """Clear an agent session's conversation history.

    Use this to reset the conversation state for any agent.

    Args:
        agent_id: Agent ID
        session_id: Session ID to clear (optional, defaults to user's default session)
    """
    sess_key = session_id or f"{user_id}:agent:{agent_id}"
    agent_service.clear_direct_session(sess_key)
    return None


# =============================================================================
# WORKFLOW ENDPOINTS
# Multi-agent orchestration with supervisor
# =============================================================================

# Create a separate router for workflows
workflow_router = APIRouter(prefix="/workflows", tags=["workflows"])


@workflow_router.get("", response_model=list[WorkflowInfo])
def list_workflows(
    agent_service: AgentService = Depends(get_agent_service),
):
    """List all active multi-agent workflows.

    Returns:
        List of workflow information
    """
    return agent_service.list_workflows()


@workflow_router.post("", response_model=WorkflowCreateResponse, status_code=201)
def create_workflow(
    request: WorkflowCreateRequest,
    agent_service: AgentService = Depends(get_agent_service),
):
    """Create a new multi-agent workflow with supervisor.

    The workflow coordinates multiple specialized agents to handle complex tasks.

    Args:
        request: Workflow configuration

    Returns:
        Created workflow information
    """
    workflow_id = request.workflow_id or str(uuid.uuid4())

    try:
        agent_service.create_workflow(
            workflow_id=workflow_id,
            agent_names=request.agents,
            provider=request.provider,
            model=request.model,
            supervisor_prompt=request.supervisor_prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return WorkflowCreateResponse(
        workflow_id=workflow_id,
        agents=request.agents,
        message=f"Workflow created with {len(request.agents)} agents",
    )


@workflow_router.post("/{workflow_id}/invoke", response_model=WorkflowInvokeResponse)
def invoke_workflow(
    workflow_id: str,
    request: WorkflowInvokeRequest,
    user_id: str = Depends(get_current_user_id),
    agent_service: AgentService = Depends(get_agent_service),
):
    """Invoke a multi-agent workflow.

    The supervisor will delegate the task to appropriate specialized agents.
    Sessions are persisted and support memory summarization for long conversations.

    Args:
        workflow_id: ID of the workflow to invoke
        request: Message to process with memory options and optional images

    Returns:
        Workflow response with session_id and memory metadata
    """
    session_id = request.session_id or f"{user_id}:workflow:{workflow_id}"

    try:
        result = agent_service.invoke_workflow(
            workflow_id=workflow_id,
            message=request.message,
            images=request.images,
            session_id=session_id,
            user_id=user_id,
            enable_memory=request.enable_memory,
            memory_trigger_count=request.memory_trigger_count,
            memory_keep_recent=request.memory_keep_recent,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return WorkflowInvokeResponse(**result)


@workflow_router.post("/{workflow_id}/invoke/stream")
async def invoke_workflow_stream(
    workflow_id: str,
    request: WorkflowInvokeRequest,
    user_id: str = Depends(get_current_user_id),
    agent_service: AgentService = Depends(get_agent_service),
):
    """Stream responses from a multi-agent workflow.

    This endpoint streams SSE events for agent delegation, tool calls, and tokens.
    Use this to show real-time multi-agent coordination and responses.

    Events:
        - start: Initial event with session and workflow info
        - agent_start: When a specialist agent begins processing
        - agent_end: When a specialist agent completes
        - tool_call: When a tool is called by an agent
        - tool_result: Result of a tool call
        - token: Streaming text token
        - done: Final event with complete response
        - error: If an error occurs

    Args:
        workflow_id: ID of the workflow to invoke
        request: Message to process with memory options and optional images

    Returns:
        SSE stream of events
    """
    session_id = request.session_id or f"{user_id}:workflow:{workflow_id}"

    async def event_generator():
        async for event in agent_service.stream_workflow(
            workflow_id=workflow_id,
            message=request.message,
            images=request.images,
            session_id=session_id,
            user_id=user_id,
            enable_memory=request.enable_memory,
            memory_trigger_count=request.memory_trigger_count,
            memory_keep_recent=request.memory_keep_recent,
        ):
            yield {
                "event": event.get("event", "message"),
                "data": event.get("data", "{}"),
            }

    return EventSourceResponse(event_generator())


@workflow_router.delete("/{workflow_id}", response_model=WorkflowDeleteResponse)
def delete_workflow(
    workflow_id: str,
    agent_service: AgentService = Depends(get_agent_service),
):
    """Delete a multi-agent workflow.

    Args:
        workflow_id: ID of the workflow to delete

    Returns:
        Deletion status
    """
    deleted = agent_service.delete_workflow(workflow_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")

    return WorkflowDeleteResponse(
        workflow_id=workflow_id,
        deleted=True,
    )
