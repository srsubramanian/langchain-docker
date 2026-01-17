"""Chat API endpoints."""

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from langchain_docker.api.dependencies import get_chat_service, get_current_user_id
from langchain_docker.api.schemas.chat import ChatRequest, ChatResponse
from langchain_docker.api.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
):
    """Process a chat message (non-streaming).

    Args:
        request: Chat request with message and configuration

    Returns:
        Chat response with AI message
    """
    return chat_service.process_message(request, user_id=user_id)


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
):
    """Process a chat message with streaming response.

    Args:
        request: Chat request with message and configuration

    Returns:
        Server-Sent Events stream with tokens
    """
    return EventSourceResponse(chat_service.stream_message(request, user_id=user_id))
