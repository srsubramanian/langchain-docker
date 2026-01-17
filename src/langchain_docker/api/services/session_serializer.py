"""Session serialization utilities for Redis storage.

Provides functions to serialize and deserialize LangChain BaseMessage
objects and Session dataclasses to/from JSON for Redis storage.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

if TYPE_CHECKING:
    from langchain_docker.api.services.session_service import Session


def serialize_message(msg: BaseMessage) -> dict:
    """Serialize a LangChain message to JSON-compatible dict.

    Args:
        msg: LangChain BaseMessage instance

    Returns:
        Dictionary with type, content, and additional_kwargs
    """
    return {
        "type": msg.__class__.__name__,
        "content": msg.content,
        "additional_kwargs": msg.additional_kwargs,
    }


def deserialize_message(data: dict) -> BaseMessage:
    """Deserialize a dict to LangChain message.

    Args:
        data: Dictionary with type, content, and optional additional_kwargs

    Returns:
        Appropriate BaseMessage subclass instance
    """
    msg_type = data.get("type", "HumanMessage")
    content = data.get("content", "")
    kwargs = data.get("additional_kwargs", {})

    if msg_type == "HumanMessage":
        return HumanMessage(content=content, additional_kwargs=kwargs)
    elif msg_type == "AIMessage":
        return AIMessage(content=content, additional_kwargs=kwargs)
    elif msg_type == "SystemMessage":
        return SystemMessage(content=content, additional_kwargs=kwargs)
    else:
        # Default to HumanMessage for unknown types
        return HumanMessage(content=content, additional_kwargs=kwargs)


def serialize_session(session: Session) -> str:
    """Serialize entire Session to JSON string.

    Args:
        session: Session dataclass instance

    Returns:
        JSON string representation of the session
    """
    return json.dumps({
        "session_id": session.session_id,
        "user_id": session.user_id,
        "messages": [serialize_message(m) for m in session.messages],
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "metadata": session.metadata,
        "conversation_summary": session.conversation_summary,
        "summary_message_count": session.summary_message_count,
        "last_summarized_at": (
            session.last_summarized_at.isoformat()
            if session.last_summarized_at
            else None
        ),
        "session_type": session.session_type,
    })


def deserialize_session(data: str) -> Session:
    """Deserialize JSON string to Session object.

    Args:
        data: JSON string representation of session

    Returns:
        Session dataclass instance
    """
    # Import here to avoid circular imports
    from langchain_docker.api.services.session_service import Session

    obj = json.loads(data)
    return Session(
        session_id=obj["session_id"],
        user_id=obj["user_id"],
        messages=[deserialize_message(m) for m in obj["messages"]],
        created_at=datetime.fromisoformat(obj["created_at"]),
        updated_at=datetime.fromisoformat(obj["updated_at"]),
        metadata=obj.get("metadata", {}),
        conversation_summary=obj.get("conversation_summary"),
        summary_message_count=obj.get("summary_message_count", 0),
        last_summarized_at=(
            datetime.fromisoformat(obj["last_summarized_at"])
            if obj.get("last_summarized_at")
            else None
        ),
        session_type=obj.get("session_type", "chat"),
    )
