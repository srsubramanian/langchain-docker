"""Multi-agent API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException

from langchain_docker.api.dependencies import get_agent_service
from langchain_docker.api.schemas.agents import (
    AgentInfo,
    WorkflowCreateRequest,
    WorkflowCreateResponse,
    WorkflowDeleteResponse,
    WorkflowInfo,
    WorkflowInvokeRequest,
    WorkflowInvokeResponse,
)
from langchain_docker.api.services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


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
    try:
        result = agent_service.invoke_workflow(
            workflow_id=workflow_id,
            message=request.message,
            session_id=request.session_id,
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
