"""Chainlit UI for LangChain Docker API.

This app provides a chat interface that connects to the FastAPI backend.
"""

import chainlit as cl
from chainlit.input_widget import Select, Slider

from utils import get_api_client


# Initialize API client
api_client = get_api_client()


@cl.on_chat_start
async def start():
    """Initialize chat session when a new chat starts."""
    # Check API health
    try:
        health = await api_client.health_check()
        await cl.Message(
            content=f"Connected to API backend (version: {health.get('version', 'unknown')})",
            author="System",
        ).send()
    except Exception as e:
        await cl.Message(
            content=f"Warning: Could not connect to API backend: {str(e)}",
            author="System",
        ).send()
        return

    # Create a new backend session explicitly
    try:
        session_response = await api_client.create_session(
            metadata={"source": "chainlit", "user": cl.user_session.get("id", "unknown")}
        )
        session_id = session_response.get("session_id")
        cl.user_session.set("session_id", session_id)

        await cl.Message(
            content=f"✓ Session created: `{session_id}`\n\nThis session ID will group all your messages together in Phoenix tracing.",
            author="System",
        ).send()
    except Exception as e:
        await cl.Message(
            content=f"Warning: Could not create session: {str(e)}",
            author="System",
        ).send()
        cl.user_session.set("session_id", None)

    # Get available providers
    try:
        providers = await api_client.list_providers()
        configured_providers = [
            p["name"] for p in providers if p.get("configured", False)
        ]

        if not configured_providers:
            await cl.Message(
                content="No providers are configured. Please set up API keys in your .env file.",
                author="System",
            ).send()
            return

        # Display configured providers
        provider_list = ", ".join(configured_providers)
        await cl.Message(
            content=f"Available providers: {provider_list}",
            author="System",
        ).send()

    except Exception as e:
        await cl.Message(
            content=f"Could not fetch providers: {str(e)}",
            author="System",
        ).send()

    # Initialize other session state
    cl.user_session.set("provider", "openai")
    cl.user_session.set("model", None)
    cl.user_session.set("temperature", 0.7)

    # Configure chat settings
    settings = await cl.ChatSettings(
        [
            Select(
                id="provider",
                label="Model Provider",
                values=["openai", "anthropic", "google"],
                initial_value="openai",
            ),
            Slider(
                id="temperature",
                label="Temperature",
                initial=0.7,
                min=0.0,
                max=2.0,
                step=0.1,
            ),
        ]
    ).send()


@cl.on_settings_update
async def settings_update(settings):
    """Handle settings updates."""
    cl.user_session.set("provider", settings["provider"])
    cl.user_session.set("temperature", settings["temperature"])

    await cl.Message(
        content=f"Settings updated: Provider={settings['provider']}, Temperature={settings['temperature']}",
        author="System",
    ).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages."""
    # Get current settings
    provider = cl.user_session.get("provider")
    model = cl.user_session.get("model")
    temperature = cl.user_session.get("temperature")
    session_id = cl.user_session.get("session_id")

    # Create response message
    msg = cl.Message(content="", author="Assistant")
    await msg.send()

    try:
        # Stream response from API
        full_response = ""
        async for event in api_client.chat_stream(
            message=message.content,
            session_id=session_id,
            provider=provider,
            model=model,
            temperature=temperature,
        ):
            event_type = event.get("event")

            if event_type == "start":
                # Session already created explicitly, just continue
                pass

            elif event_type == "token":
                # Stream token to UI
                token = event.get("content", "")
                full_response += token
                await msg.stream_token(token)

            elif event_type == "done":
                # Finalize message
                message_count = event.get("message_count", 0)
                await msg.update()
                # Don't break - let the generator finish naturally

            elif event_type == "error":
                # Handle error
                error_msg = event.get("message", "Unknown error occurred")
                await msg.stream_token(f"\n\nError: {error_msg}")
                await msg.update()
                # Don't break - let the generator finish naturally

    except Exception as e:
        error_message = f"Error communicating with API: {str(e)}"
        await msg.stream_token(error_message)
        await msg.update()


@cl.on_chat_end
async def end():
    """Handle chat end."""
    session_id = cl.user_session.get("session_id")
    if session_id:
        await cl.Message(
            content=f"Session {session_id} ended. Your conversation history is saved on the backend.",
            author="System",
        ).send()


@cl.action_callback("reset_session")
async def on_reset_session(action: cl.Action):
    """Reset the current session."""
    # Create a new session
    try:
        session_response = await api_client.create_session(
            metadata={"source": "chainlit", "user": cl.user_session.get("id", "unknown"), "reset": True}
        )
        session_id = session_response.get("session_id")
        cl.user_session.set("session_id", session_id)

        await cl.Message(
            content=f"Session reset! New session created: `{session_id}`",
            author="System",
        ).send()
    except Exception as e:
        cl.user_session.set("session_id", None)
        await cl.Message(
            content=f"Session reset but could not create new session: {str(e)}",
            author="System",
        ).send()


@cl.action_callback("show_session_info")
async def on_show_session_info(action: cl.Action):
    """Show current session information."""
    session_id = cl.user_session.get("session_id")
    if session_id:
        await cl.Message(
            content=f"**Current Session Info:**\n\n"
            f"- Session ID: `{session_id}`\n"
            f"- View in Phoenix: http://localhost:6006 (Sessions tab)\n"
            f"- Search for: `{session_id}`",
            author="System",
        ).send()
    else:
        await cl.Message(
            content="No active session",
            author="System",
        ).send()
