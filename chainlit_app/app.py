"""Chainlit UI for LangChain Docker API.

This app provides a chat interface that connects to the FastAPI backend.
Supports both standard chat, multi-agent workflows, and custom agent creation.
"""

import uuid

import chainlit as cl
from chainlit.input_widget import Select, Slider, Switch

from utils import get_api_client


# Initialize API client
api_client = get_api_client()

# Agent presets for multi-agent mode (built-in)
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

# Agent Builder wizard steps
BUILDER_STEPS = ["name", "prompt", "tools", "confirm"]


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

    # Fetch custom agents and build dynamic presets
    available_presets = dict(AGENT_PRESETS)  # Start with built-in presets
    try:
        custom_agents = await api_client.list_custom_agents()
        for agent in custom_agents:
            preset_key = f"custom:{agent['id']}"
            available_presets[preset_key] = {
                "name": f"Custom: {agent['name']}",
                "agents": [agent["id"]],
                "description": agent.get("description", "Custom agent"),
            }
        if custom_agents:
            await cl.Message(
                content=f"Custom agents available: {', '.join([a['name'] for a in custom_agents])}",
                author="System",
            ).send()
    except Exception:
        pass  # Custom agents not critical

    # Initialize session state
    cl.user_session.set("provider", configured_providers[0] if configured_providers else "openai")
    cl.user_session.set("model", None)
    cl.user_session.set("temperature", 0.7)
    cl.user_session.set("mode", "chat")  # "chat" or "multi_agent"
    cl.user_session.set("agent_preset", "all")
    cl.user_session.set("workflow_id", None)
    cl.user_session.set("available_presets", available_presets)  # Store dynamic presets

    # Initialize agent builder state
    cl.user_session.set("builder_active", False)
    cl.user_session.set("builder_step", None)
    cl.user_session.set("builder_data", {})

    # Show agent builder action buttons
    actions = [
        cl.Action(
            name="create_agent",
            payload={"action": "create"},
            label="Create Custom Agent",
        ),
        cl.Action(
            name="view_tools",
            payload={"action": "tools"},
            label="View Available Tools",
        ),
        cl.Action(
            name="my_agents",
            payload={"action": "agents"},
            label="My Custom Agents",
        ),
    ]
    await cl.Message(
        content="**Agent Builder**: Create custom agents with your choice of tools",
        author="System",
        actions=actions,
    ).send()

    # Configure chat settings with mode selection
    preset_keys = list(available_presets.keys())
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
                values=preset_keys,
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
    available_presets = cl.user_session.get("available_presets", AGENT_PRESETS)
    preset = available_presets.get(preset_key, available_presets.get("all", AGENT_PRESETS["all"]))
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
    # Check if agent builder wizard is active
    if cl.user_session.get("builder_active"):
        await _handle_builder_message(message)
        return

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


# Agent Builder Action Callbacks


@cl.action_callback("create_agent")
async def on_create_agent(action: cl.Action):
    """Start the agent builder wizard."""
    cl.user_session.set("builder_active", True)
    cl.user_session.set("builder_step", "name")
    cl.user_session.set("builder_data", {})

    await cl.Message(
        content="**Agent Builder Wizard**\n\n"
                "Let's create a custom agent! You can cancel at any time by typing `cancel`.\n\n"
                "**Step 1/4: Name**\n"
                "What would you like to name your agent?",
        author="Agent Builder",
    ).send()


@cl.action_callback("view_tools")
async def on_view_tools(action: cl.Action):
    """Show available tool templates."""
    try:
        tools = await api_client.list_tool_templates()
        categories = await api_client.list_tool_categories()

        content = "**Available Tool Templates**\n\n"

        for category in categories:
            category_tools = [t for t in tools if t["category"] == category]
            if category_tools:
                content += f"### {category.title()}\n"
                for tool in category_tools:
                    content += f"- **{tool['id']}**: {tool['description']}\n"
                content += "\n"

        content += "_Use these tool IDs when creating a custom agent._"

        await cl.Message(content=content, author="System").send()
    except Exception as e:
        await cl.Message(
            content=f"Could not fetch tools: {str(e)}",
            author="System",
        ).send()


@cl.action_callback("my_agents")
async def on_my_agents(action: cl.Action):
    """Show user's custom agents."""
    try:
        agents = await api_client.list_custom_agents()

        if not agents:
            await cl.Message(
                content="**My Custom Agents**\n\n"
                        "_No custom agents created yet. Click 'Create Custom Agent' to get started!_",
                author="System",
            ).send()
            return

        content = "**My Custom Agents**\n\n"
        for agent in agents:
            tools_str = ", ".join(agent["tools"])
            content += f"### {agent['name']}\n"
            content += f"- **ID**: `{agent['id']}`\n"
            content += f"- **Tools**: {tools_str}\n"
            content += f"- **Description**: {agent['description']}\n"
            content += f"- **Created**: {agent['created_at']}\n\n"

        content += "_Use the agent ID in the Multi-Agent mode preset selector to use your custom agent._"

        # Add delete buttons for each agent
        actions = [
            cl.Action(
                name="delete_agent",
                payload={"agent_id": agent["id"]},
                label=f"Delete {agent['name']}",
            )
            for agent in agents
        ]

        await cl.Message(content=content, author="System", actions=actions).send()
    except Exception as e:
        await cl.Message(
            content=f"Could not fetch custom agents: {str(e)}",
            author="System",
        ).send()


@cl.action_callback("delete_agent")
async def on_delete_agent(action: cl.Action):
    """Delete a custom agent."""
    agent_id = action.payload.get("agent_id")
    if not agent_id:
        return

    try:
        await api_client.delete_custom_agent(agent_id)
        await cl.Message(
            content=f"Agent `{agent_id}` deleted successfully.",
            author="System",
        ).send()
    except Exception as e:
        await cl.Message(
            content=f"Could not delete agent: {str(e)}",
            author="System",
        ).send()


@cl.action_callback("cancel_builder")
async def on_cancel_builder(action: cl.Action):
    """Cancel the agent builder wizard."""
    cl.user_session.set("builder_active", False)
    cl.user_session.set("builder_step", None)
    cl.user_session.set("builder_data", {})

    await cl.Message(
        content="Agent builder cancelled.",
        author="System",
    ).send()


# Agent Builder Wizard Handler


async def _handle_builder_message(message: cl.Message):
    """Handle messages during agent builder wizard."""
    user_input = message.content.strip()
    step = cl.user_session.get("builder_step")
    data = cl.user_session.get("builder_data", {})

    # Handle cancel at any point
    if user_input.lower() == "cancel":
        cl.user_session.set("builder_active", False)
        cl.user_session.set("builder_step", None)
        cl.user_session.set("builder_data", {})
        await cl.Message(
            content="Agent builder cancelled.",
            author="Agent Builder",
        ).send()
        return

    if step == "name":
        # Validate name
        if len(user_input) < 1 or len(user_input) > 50:
            await cl.Message(
                content="Name must be between 1 and 50 characters. Please try again:",
                author="Agent Builder",
            ).send()
            return

        data["name"] = user_input
        cl.user_session.set("builder_data", data)
        cl.user_session.set("builder_step", "prompt")

        await cl.Message(
            content=f"Great! Your agent will be named **{user_input}**.\n\n"
                    "**Step 2/4: System Prompt**\n"
                    "Write a system prompt that defines your agent's behavior and personality.\n"
                    "(Minimum 10 characters)",
            author="Agent Builder",
        ).send()

    elif step == "prompt":
        # Validate prompt
        if len(user_input) < 10:
            await cl.Message(
                content="System prompt must be at least 10 characters. Please try again:",
                author="Agent Builder",
            ).send()
            return

        data["system_prompt"] = user_input
        cl.user_session.set("builder_data", data)
        cl.user_session.set("builder_step", "tools")

        # Show available tools
        try:
            tools = await api_client.list_tool_templates()
            tool_list = "\n".join([f"- **{t['id']}**: {t['description']}" for t in tools])

            await cl.Message(
                content=f"System prompt saved.\n\n"
                        f"**Step 3/4: Select Tools**\n"
                        f"Choose the tools for your agent from the list below.\n"
                        f"Enter tool IDs separated by commas (e.g., `add, multiply, get_weather`).\n\n"
                        f"**Available Tools:**\n{tool_list}",
                author="Agent Builder",
            ).send()
        except Exception as e:
            await cl.Message(
                content=f"System prompt saved, but could not fetch tools: {str(e)}\n"
                        "Enter tool IDs separated by commas:",
                author="Agent Builder",
            ).send()

    elif step == "tools":
        # Parse tool IDs
        tool_ids = [t.strip() for t in user_input.split(",") if t.strip()]

        if not tool_ids:
            await cl.Message(
                content="Please select at least one tool. Enter tool IDs separated by commas:",
                author="Agent Builder",
            ).send()
            return

        # Validate tools exist
        try:
            available_tools = await api_client.list_tool_templates()
            available_ids = [t["id"] for t in available_tools]

            invalid_tools = [t for t in tool_ids if t not in available_ids]
            if invalid_tools:
                await cl.Message(
                    content=f"Unknown tools: {', '.join(invalid_tools)}\n"
                            f"Available tools: {', '.join(available_ids)}\n"
                            "Please try again:",
                    author="Agent Builder",
                ).send()
                return
        except Exception:
            pass  # Continue anyway

        data["tools"] = [{"tool_id": tid, "config": {}} for tid in tool_ids]
        cl.user_session.set("builder_data", data)
        cl.user_session.set("builder_step", "confirm")

        tool_names = ", ".join(tool_ids)
        await cl.Message(
            content=f"**Step 4/4: Confirm**\n\n"
                    f"Please review your agent configuration:\n\n"
                    f"- **Name**: {data['name']}\n"
                    f"- **System Prompt**: {data['system_prompt'][:100]}{'...' if len(data['system_prompt']) > 100 else ''}\n"
                    f"- **Tools**: {tool_names}\n\n"
                    f"Type `create` to create the agent, or `cancel` to abort.",
            author="Agent Builder",
        ).send()

    elif step == "confirm":
        if user_input.lower() == "create":
            # Create the agent
            try:
                result = await api_client.create_custom_agent(
                    name=data["name"],
                    system_prompt=data["system_prompt"],
                    tools=data["tools"],
                )

                agent_id = result.get("agent_id", "unknown")

                # Reset wizard state
                cl.user_session.set("builder_active", False)
                cl.user_session.set("builder_step", None)
                cl.user_session.set("builder_data", {})

                # Update available presets with new agent
                available_presets = cl.user_session.get("available_presets", dict(AGENT_PRESETS))
                preset_key = f"custom:{agent_id}"
                available_presets[preset_key] = {
                    "name": f"Custom: {data['name']}",
                    "agents": [agent_id],
                    "description": data["system_prompt"][:100],
                }
                cl.user_session.set("available_presets", available_presets)

                await cl.Message(
                    content=f"**Agent Created Successfully!**\n\n"
                            f"- **Name**: {data['name']}\n"
                            f"- **ID**: `{agent_id}`\n"
                            f"- **Tools**: {', '.join([t['tool_id'] for t in data['tools']])}\n\n"
                            f"**To use this agent:**\n"
                            f"1. Open Settings (gear icon)\n"
                            f"2. Set Mode to 'Multi-Agent'\n"
                            f"3. Select `custom:{agent_id}` from Agent Team dropdown\n\n"
                            f"_Note: Refresh the page if you don't see it in the dropdown._",
                    author="Agent Builder",
                ).send()

            except Exception as e:
                await cl.Message(
                    content=f"Failed to create agent: {str(e)}\n"
                            "Type `create` to try again, or `cancel` to abort.",
                    author="Agent Builder",
                ).send()
        else:
            await cl.Message(
                content="Type `create` to create the agent, or `cancel` to abort.",
                author="Agent Builder",
            ).send()
