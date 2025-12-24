"""Utility functions for Chainlit app to communicate with FastAPI backend."""

import logging
import os
from typing import AsyncGenerator, Optional

import httpx

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class APIClient:
    """Client for communicating with the FastAPI backend."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize API client.

        Args:
            base_url: Base URL of the FastAPI backend
        """
        self.base_url = base_url
        self.timeout = httpx.Timeout(60.0, connect=5.0)

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        provider: str = "openai",
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> dict:
        """Send a non-streaming chat message.

        Args:
            message: User message
            session_id: Optional session ID for conversation history
            provider: Model provider (openai, anthropic, google)
            model: Model name (optional, uses provider default)
            temperature: Temperature for response generation

        Returns:
            Response from the API containing the assistant's message
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "message": message,
                "provider": provider,
                "temperature": temperature,
                "stream": False,
            }
            if session_id:
                payload["session_id"] = session_id
            if model:
                payload["model"] = model

            response = await client.post(
                f"{self.base_url}/api/v1/chat",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def chat_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        provider: str = "openai",
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[dict, None]:
        """Send a streaming chat message using SSE.

        Args:
            message: User message
            session_id: Optional session ID for conversation history
            provider: Model provider (openai, anthropic, google)
            model: Model name (optional, uses provider default)
            temperature: Temperature for response generation

        Yields:
            Events from the streaming response
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "message": message,
                "provider": provider,
                "temperature": temperature,
                "stream": True,
            }
            if session_id:
                payload["session_id"] = session_id
            if model:
                payload["model"] = model

            logger.debug(f"[chat_stream] POST {self.base_url}/api/v1/chat/stream")
            logger.debug(f"[chat_stream] Payload: {payload}")

            async with client.stream(
                "POST",
                f"{self.base_url}/api/v1/chat/stream",
                json=payload,
            ) as response:
                response.raise_for_status()
                current_event = None
                async for line in response.aiter_lines():
                    line = line.strip()
                    if line.startswith("event: "):
                        current_event = line[7:]  # Remove "event: " prefix
                    elif line.startswith("data: "):
                        import json

                        try:
                            data = json.loads(line[6:])  # Remove "data: " prefix
                            if current_event:
                                data["event"] = current_event
                            yield data
                        except json.JSONDecodeError:
                            continue

    async def create_session(self, metadata: Optional[dict] = None) -> dict:
        """Create a new session.

        Args:
            metadata: Optional metadata for the session

        Returns:
            Session information including session_id
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {"metadata": metadata or {}}
            logger.debug(f"[create_session] POST {self.base_url}/api/v1/sessions")
            logger.debug(f"[create_session] Payload: {payload}")
            response = await client.post(
                f"{self.base_url}/api/v1/sessions",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            logger.debug(f"[create_session] Response: {result}")
            return result

    async def get_session(self, session_id: str) -> dict:
        """Get session details including message history.

        Args:
            session_id: Session ID to retrieve

        Returns:
            Session information including messages
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/sessions/{session_id}"
            )
            response.raise_for_status()
            return response.json()

    async def list_providers(self) -> list[dict]:
        """List all available model providers.

        Returns:
            List of provider information
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/api/v1/models/providers")
            response.raise_for_status()
            return response.json()

    async def get_provider_details(self, provider: str) -> dict:
        """Get details for a specific provider.

        Args:
            provider: Provider name (openai, anthropic, google)

        Returns:
            Provider details including available models
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/models/providers/{provider}"
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> dict:
        """Check if the API backend is healthy.

        Returns:
            Health status information
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    # Multi-Agent Workflow Methods

    async def list_builtin_agents(self) -> list[dict]:
        """List all available built-in agents.

        Returns:
            List of agent information with name, tools, and description
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/api/v1/agents/builtin")
            response.raise_for_status()
            return response.json()

    async def list_workflows(self) -> list[dict]:
        """List all active workflows.

        Returns:
            List of workflow information
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/api/v1/agents/workflows")
            response.raise_for_status()
            return response.json()

    async def create_workflow(
        self,
        workflow_id: str,
        agents: list[str],
        provider: str = "openai",
        model: Optional[str] = None,
        supervisor_prompt: Optional[str] = None,
    ) -> dict:
        """Create a multi-agent workflow.

        Args:
            workflow_id: Unique identifier for the workflow
            agents: List of agent names to include
            provider: Model provider to use
            model: Optional model name
            supervisor_prompt: Optional custom supervisor prompt

        Returns:
            Workflow creation response
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "workflow_id": workflow_id,
                "agents": agents,
                "provider": provider,
            }
            if model:
                payload["model"] = model
            if supervisor_prompt:
                payload["supervisor_prompt"] = supervisor_prompt

            logger.debug(f"[create_workflow] POST {self.base_url}/api/v1/agents/workflows")
            logger.debug(f"[create_workflow] Payload: {payload}")

            response = await client.post(
                f"{self.base_url}/api/v1/agents/workflows",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def invoke_workflow(
        self,
        workflow_id: str,
        message: str,
        session_id: Optional[str] = None,
    ) -> dict:
        """Invoke a multi-agent workflow.

        Args:
            workflow_id: Workflow to invoke
            message: User message
            session_id: Optional session ID for tracing

        Returns:
            Workflow response with agent output
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {"message": message}
            if session_id:
                payload["session_id"] = session_id

            logger.debug(f"[invoke_workflow] POST {self.base_url}/api/v1/agents/workflows/{workflow_id}/invoke")
            logger.debug(f"[invoke_workflow] Payload: {payload}")

            response = await client.post(
                f"{self.base_url}/api/v1/agents/workflows/{workflow_id}/invoke",
                json=payload,
                timeout=120.0,  # Longer timeout for multi-agent
            )
            response.raise_for_status()
            return response.json()

    async def delete_workflow(self, workflow_id: str) -> dict:
        """Delete a workflow.

        Args:
            workflow_id: Workflow to delete

        Returns:
            Deletion response
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(
                f"{self.base_url}/api/v1/agents/workflows/{workflow_id}"
            )
            response.raise_for_status()
            return response.json()


def get_api_client() -> APIClient:
    """Get API client instance.

    Returns:
        APIClient configured with BASE_URL from environment or default
    """
    base_url = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
    return APIClient(base_url=base_url)
