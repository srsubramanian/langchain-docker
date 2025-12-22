"""Chat API endpoints."""

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from langchain_docker.api.dependencies import get_chat_service
from langchain_docker.api.schemas.chat import ChatRequest, ChatResponse
from langchain_docker.api.services.chat_service import ChatService
from langchain_docker.core.config import load_environment

# Load environment variables once at module import
load_environment()

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    """Process a chat message (non-streaming).

    Args:
        request: Chat request with message and configuration

    Returns:
        Chat response with AI message
    """
    return chat_service.process_message(request)


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    """Process a chat message with streaming response.

    Args:
        request: Chat request with message and configuration

    Returns:
        Server-Sent Events stream with tokens
    """
    return EventSourceResponse(chat_service.stream_message(request))
