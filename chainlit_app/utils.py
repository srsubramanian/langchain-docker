"""Utility functions for Chainlit app to communicate with FastAPI backend."""

import os
from typing import AsyncGenerator, Optional

import httpx


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

            async with client.stream(
                "POST",
                f"{self.base_url}/api/v1/chat/stream",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        import json

                        try:
                            data = json.loads(line[6:])  # Remove "data: " prefix
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
            response = await client.post(
                f"{self.base_url}/api/v1/sessions",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

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


def get_api_client() -> APIClient:
    """Get API client instance.

    Returns:
        APIClient configured with BASE_URL from environment or default
    """
    base_url = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
    return APIClient(base_url=base_url)
