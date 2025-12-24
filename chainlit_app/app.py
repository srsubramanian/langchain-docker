"""Chainlit UI for LangChain Docker API.

This app provides a chat interface that connects to the FastAPI backend.
Supports both standard chat and multi-agent workflows.
"""

import uuid

import chainlit as cl
from chainlit.input_widget import Select, Slider, Switch

from utils import get_api_client


# Initialize API client
api_client = get_api_client()

# Agent presets for multi-agent mode
AGENT_PRESETS = {
    "all": {
        "name": "All Agents",
        "agents": ["math_expert", "weather_expert", "research_expert", "finance_expert"],
        "description": "Use all available agents (math, weather, research, finance)",
    },
    "math_weather": {
        "name": "Math + Weather",
        "agents": ["math_expert", "weather_expert"],
        "description": "Math calculations and weather queries",
    },
    "research_finance": {
        "name": "Research + Finance",
        "agents": ["research_expert", "finance_expert"],
        "description": "Web research and stock prices",
    },
    "math_only": {
        "name": "Math Expert",
        "agents": ["math_expert"],
        "description": "Mathematical calculations only",
    },
}


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
            content=f"Session created: `{session_id}`",
            author="System",
        ).send()
    except Exception as e:
        await cl.Message(
            content=f"Warning: Could not create session: {str(e)}",
            author="System",
        ).send()
        cl.user_session.set("session_id", None)

    # Get available providers
    configured_providers = ["openai"]  # Default
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

    # Check for available agents
    try:
        agents = await api_client.list_builtin_agents()
        agent_names = [a["name"] for a in agents]
        await cl.Message(
            content=f"Multi-agent mode available with: {', '.join(agent_names)}",
            author="System",
        ).send()
    except Exception:
        pass  # Multi-agent not critical

    # Initialize session state
    cl.user_session.set("provider", configured_providers[0] if configured_providers else "openai")
    cl.user_session.set("model", None)
    cl.user_session.set("temperature", 0.7)
    cl.user_session.set("mode", "chat")  # "chat" or "multi_agent"
    cl.user_session.set("agent_preset", "all")
    cl.user_session.set("workflow_id", None)

    # Configure chat settings with mode selection
    settings = await cl.ChatSettings(
        [
            Select(
                id="mode",
                label="Mode",
                values=["Standard Chat", "Multi-Agent"],
                initial_value="Standard Chat",
            ),
            Select(
                id="agent_preset",
                label="Agent Team (Multi-Agent mode)",
                values=list(AGENT_PRESETS.keys()),
                initial_value="all",
            ),
            Select(
                id="provider",
                label="Model Provider",
                values=configured_providers if configured_providers else ["openai", "anthropic", "google"],
                initial_value=configured_providers[0] if configured_providers else "openai",
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
    old_mode = cl.user_session.get("mode")
    new_mode = "multi_agent" if settings["mode"] == "Multi-Agent" else "chat"

    cl.user_session.set("provider", settings["provider"])
    cl.user_session.set("temperature", settings["temperature"])
    cl.user_session.set("mode", new_mode)
    cl.user_session.set("agent_preset", settings["agent_preset"])

    # Handle mode change
    if new_mode == "multi_agent" and old_mode != "multi_agent":
        # Entering multi-agent mode - create workflow
        await _create_workflow_for_session(settings["agent_preset"], settings["provider"])
    elif new_mode == "chat" and old_mode == "multi_agent":
        # Leaving multi-agent mode - cleanup workflow
        await _cleanup_workflow()
        await cl.Message(
            content="Switched to Standard Chat mode.",
            author="System",
        ).send()
    elif new_mode == "multi_agent":
        # Still in multi-agent mode but settings changed - recreate workflow
        await _cleanup_workflow()
        await _create_workflow_for_session(settings["agent_preset"], settings["provider"])
    else:
        await cl.Message(
            content=f"Settings updated: Provider={settings['provider']}, Temperature={settings['temperature']}",
            author="System",
        ).send()


async def _create_workflow_for_session(preset_key: str, provider: str):
    """Create a multi-agent workflow for the current session."""
    preset = AGENT_PRESETS.get(preset_key, AGENT_PRESETS["all"])
    session_id = cl.user_session.get("session_id") or str(uuid.uuid4())
    workflow_id = f"chainlit-{session_id[:8]}"

    try:
        await api_client.create_workflow(
            workflow_id=workflow_id,
            agents=preset["agents"],
            provider=provider,
        )
        cl.user_session.set("workflow_id", workflow_id)

        agent_list = ", ".join(preset["agents"])
        await cl.Message(
            content=f"**Multi-Agent Mode Activated**\n\n"
                   f"Team: {preset['name']}\n"
                   f"Agents: {agent_list}\n"
                   f"Workflow ID: `{workflow_id}`\n\n"
                   f"_The supervisor will delegate your questions to the appropriate specialist agents._",
            author="System",
        ).send()
    except Exception as e:
        await cl.Message(
            content=f"Failed to create multi-agent workflow: {str(e)}\nFalling back to standard chat.",
            author="System",
        ).send()
        cl.user_session.set("mode", "chat")
        cl.user_session.set("workflow_id", None)


async def _cleanup_workflow():
    """Clean up the current workflow."""
    workflow_id = cl.user_session.get("workflow_id")
    if workflow_id:
        try:
            await api_client.delete_workflow(workflow_id)
        except Exception:
            pass  # Ignore cleanup errors
        cl.user_session.set("workflow_id", None)


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages."""
    mode = cl.user_session.get("mode", "chat")

    if mode == "multi_agent":
        await _handle_multi_agent_message(message)
    else:
        await _handle_chat_message(message)


async def _handle_chat_message(message: cl.Message):
    """Handle message in standard chat mode."""
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
                pass

            elif event_type == "token":
                token = event.get("content", "")
                full_response += token
                await msg.stream_token(token)

            elif event_type == "done":
                await msg.update()

            elif event_type == "error":
                error_msg = event.get("message", "Unknown error occurred")
                await msg.stream_token(f"\n\nError: {error_msg}")
                await msg.update()

    except Exception as e:
        error_message = f"Error communicating with API: {str(e)}"
        await msg.stream_token(error_message)
        await msg.update()


async def _handle_multi_agent_message(message: cl.Message):
    """Handle message in multi-agent mode."""
    workflow_id = cl.user_session.get("workflow_id")
    session_id = cl.user_session.get("session_id")

    if not workflow_id:
        # Workflow not created yet - create it now
        preset = cl.user_session.get("agent_preset", "all")
        provider = cl.user_session.get("provider", "openai")
        await _create_workflow_for_session(preset, provider)
        workflow_id = cl.user_session.get("workflow_id")

        if not workflow_id:
            await cl.Message(
                content="Multi-agent workflow not available. Please try again.",
                author="System",
            ).send()
            return

    # Create response message with thinking indicator
    msg = cl.Message(content="", author="Multi-Agent Team")
    await msg.send()
    await msg.stream_token("_Agents are working on your request..._\n\n")

    try:
        # Invoke workflow (non-streaming for now)
        result = await api_client.invoke_workflow(
            workflow_id=workflow_id,
            message=message.content,
            session_id=session_id,
        )

        # Clear the thinking message and show response
        response = result.get("response", "No response from agents")
        agents_used = result.get("agents", [])
        message_count = result.get("message_count", 0)

        # Update message with actual response
        msg.content = response
        await msg.update()

        # Show agent info as a subtle footer
        await cl.Message(
            content=f"_Processed by: {', '.join(agents_used)} | Messages: {message_count}_",
            author="System",
        ).send()

    except Exception as e:
        error_message = f"Error from multi-agent workflow: {str(e)}"
        msg.content = error_message
        await msg.update()


@cl.on_chat_end
async def end():
    """Handle chat end."""
    # Cleanup workflow if exists
    await _cleanup_workflow()

    session_id = cl.user_session.get("session_id")
    if session_id:
        await cl.Message(
            content=f"Session {session_id} ended. Your conversation history is saved.",
            author="System",
        ).send()


@cl.action_callback("reset_session")
async def on_reset_session(action: cl.Action):
    """Reset the current session."""
    # Cleanup any existing workflow
    await _cleanup_workflow()

    # Create a new session
    try:
        session_response = await api_client.create_session(
            metadata={"source": "chainlit", "user": cl.user_session.get("id", "unknown"), "reset": True}
        )
        session_id = session_response.get("session_id")
        cl.user_session.set("session_id", session_id)
        cl.user_session.set("mode", "chat")

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
    mode = cl.user_session.get("mode", "chat")
    workflow_id = cl.user_session.get("workflow_id")

    if session_id:
        info = f"**Current Session Info:**\n\n" \
               f"- Session ID: `{session_id}`\n" \
               f"- Mode: {mode.replace('_', ' ').title()}\n"

        if workflow_id:
            info += f"- Workflow ID: `{workflow_id}`\n"

        info += f"- View in Phoenix: http://localhost:6006 (Sessions tab)\n"

        await cl.Message(content=info, author="System").send()
    else:
        await cl.Message(
            content="No active session",
            author="System",
        ).send()
