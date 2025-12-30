"""Multi-agent API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException

from langchain_docker.api.dependencies import get_agent_service, get_current_user_id
from langchain_docker.api.schemas.agents import (
    AgentInfo,
    CustomAgentCreateRequest,
    CustomAgentCreateResponse,
    CustomAgentDeleteResponse,
    CustomAgentInfo,
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


# Tool Registry Endpoints


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


# Custom Agent Endpoints


@router.get("/custom", response_model=list[CustomAgentInfo])
def list_custom_agents(
    agent_service: AgentService = Depends(get_agent_service),
):
    """List all custom agents created by users.

    Returns:
        List of custom agent information
    """
    return agent_service.list_custom_agents()


@router.post("/custom", response_model=CustomAgentCreateResponse, status_code=201)
def create_custom_agent(
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

        # Build schedule config if provided
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


@router.get("/custom/{agent_id}", response_model=CustomAgentInfo)
def get_custom_agent(
    agent_id: str,
    agent_service: AgentService = Depends(get_agent_service),
):
    """Get details of a specific custom agent.

    Args:
        agent_id: Custom agent ID

    Returns:
        Custom agent information
    """
    agent = agent_service.get_custom_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Custom agent not found: {agent_id}")

    # Build schedule info if agent has a schedule
    schedule_info = None
    if agent.schedule:
        schedule_data = agent_service.get_agent_schedule(agent_id)
        schedule_info = ScheduleInfo(
            enabled=agent.schedule.enabled,
            cron_expression=agent.schedule.cron_expression,
            trigger_prompt=agent.schedule.trigger_prompt,
            timezone=agent.schedule.timezone,
            next_run=schedule_data.get("next_run") if schedule_data else None,
        )

    return CustomAgentInfo(
        id=agent.id,
        name=agent.name,
        tools=[tc["tool_id"] for tc in agent.tool_configs],
        skills=getattr(agent, "skill_ids", []) or [],
        description=agent.system_prompt[:100] + "..." if len(agent.system_prompt) > 100 else agent.system_prompt,
        schedule=schedule_info,
        created_at=agent.created_at.isoformat(),
    )


@router.delete("/custom/{agent_id}", response_model=CustomAgentDeleteResponse)
def delete_custom_agent(
    agent_id: str,
    agent_service: AgentService = Depends(get_agent_service),
):
    """Delete a custom agent.

    Args:
        agent_id: Custom agent ID to delete

    Returns:
        Deletion status
    """
    deleted = agent_service.delete_custom_agent(agent_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Custom agent not found: {agent_id}")

    return CustomAgentDeleteResponse(
        agent_id=agent_id,
        deleted=True,
    )


# Built-in Agent Endpoints


@router.get("/builtin", response_model=list[AgentInfo])
def list_builtin_agents(
    agent_service: AgentService = Depends(get_agent_service),
):
    """List all available built-in agents.

    Returns:
        List of built-in agent configurations
    """
    return agent_service.list_builtin_agents()


@router.get("/workflows", response_model=list[WorkflowInfo])
def list_workflows(
    agent_service: AgentService = Depends(get_agent_service),
):
    """List all active multi-agent workflows.

    Returns:
        List of workflow information
    """
    return agent_service.list_workflows()


@router.post("/workflows", response_model=WorkflowCreateResponse, status_code=201)
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
    # Generate workflow ID if not provided
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


@router.post("/workflows/{workflow_id}/invoke", response_model=WorkflowInvokeResponse)
def invoke_workflow(
    workflow_id: str,
    request: WorkflowInvokeRequest,
    user_id: str = Depends(get_current_user_id),
    agent_service: AgentService = Depends(get_agent_service),
):
    """Invoke a multi-agent workflow.

    The supervisor will delegate the task to appropriate specialized agents.

    Args:
        workflow_id: ID of the workflow to invoke
        request: Message to process

    Returns:
        Workflow response with agent outputs
    """
    # Include user_id in session for tracing
    session_id = request.session_id or f"{user_id}:{workflow_id}"

    try:
        result = agent_service.invoke_workflow(
            workflow_id=workflow_id,
            message=request.message,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return WorkflowInvokeResponse(**result)


@router.delete("/workflows/{workflow_id}", response_model=WorkflowDeleteResponse)
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
