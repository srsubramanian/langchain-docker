"""Agent creation and multi-turn conversation examples."""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from langchain_docker.core.config import load_environment
from langchain_docker.core.models import get_openai_model


def create_basic_agent(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
):
    """Create a basic chat agent.

    This demonstrates the simplest form of agent creation using
    a language model.

    Args:
        provider: Model provider to use
        model: Model name

    Returns:
        Initialized chat model that can be used as an agent
    """
    load_environment()

    print(f"\n{'='*60}")
    print(f"Basic Agent Creation")
    print(f"{'='*60}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    if provider == "openai":
        agent = get_openai_model(model=model)
    else:
        from langchain_docker.core.models import init_model

        agent = init_model(provider, model)

    print("✓ Agent created successfully")
    print(f"Agent type: {type(agent).__name__}\n")

    return agent


def multi_turn_conversation(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
) -> list[BaseMessage]:
    """Demonstrate multi-turn conversation with message history.

    Shows how to maintain context across multiple exchanges using
    HumanMessage and AIMessage objects.

    Args:
        provider: Model provider to use
        model: Model name

    Returns:
        List of messages in the conversation
    """
    load_environment()

    print(f"\n{'='*60}")
    print(f"Multi-Turn Conversation Example")
    print(f"{'='*60}")
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    agent = create_basic_agent(provider, model)

    messages: list[BaseMessage] = []

    # Turn 1: Introduction
    print("User: Hi, my name is Alice")
    user_message_1 = HumanMessage(content="Hi, my name is Alice")
    messages.append(user_message_1)

    response_1 = agent.invoke(messages)
    messages.append(response_1)
    print(f"Assistant: {response_1.content}\n")

    # Turn 2: Test memory
    print("User: What's my name?")
    user_message_2 = HumanMessage(content="What's my name?")
    messages.append(user_message_2)

    response_2 = agent.invoke(messages)
    messages.append(response_2)
    print(f"Assistant: {response_2.content}\n")

    # Turn 3: Follow-up question
    print("User: What was the first thing I said to you?")
    user_message_3 = HumanMessage(content="What was the first thing I said to you?")
    messages.append(user_message_3)

    response_3 = agent.invoke(messages)
    messages.append(response_3)
    print(f"Assistant: {response_3.content}\n")

    print(f"{'='*60}")
    print(f"Conversation Summary:")
    print(f"Total messages: {len(messages)}")
    print(f"Human messages: {sum(1 for m in messages if isinstance(m, HumanMessage))}")
    print(f"AI messages: {sum(1 for m in messages if isinstance(m, AIMessage))}")
    print(f"{'='*60}\n")

    return messages


def conversation_with_history() -> None:
    """Demonstrate building up conversation history progressively.

    Shows the pattern of appending messages to maintain context
    across a conversation.
    """
    load_environment()

    print(f"\n{'='*60}")
    print(f"Conversation History Pattern")
    print(f"{'='*60}\n")

    agent = get_openai_model()

    print("Building conversation step by step:\n")

    # Initialize empty conversation
    messages: list[BaseMessage] = []
    print("1. Start with empty message list")
    print(f"   messages = {messages}\n")

    # Add first user message
    messages.append(HumanMessage(content="I like pizza"))
    print("2. Add user message")
    print(f"   messages = [{type(messages[0]).__name__}(content='I like pizza')]\n")

    # Get and add AI response
    response_1 = agent.invoke(messages)
    messages.append(response_1)
    print("3. Get AI response and add to messages")
    print(f"   AI: {response_1.content[:50]}...\n")

    # Add second user message
    messages.append(HumanMessage(content="What food did I say I like?"))
    print("4. Add follow-up question")
    print(f"   User: What food did I say I like?\n")

    # Get final response (with full context)
    response_2 = agent.invoke(messages)
    messages.append(response_2)
    print("5. AI responds with context from earlier messages")
    print(f"   AI: {response_2.content}\n")

    print("Key Takeaways:")
    print("- Messages list preserves conversation history")
    print("- Always pass the full message list to maintain context")
    print("- Append each new message (both human and AI) to the list")
    print("- The model can reference earlier parts of the conversation")
    print()


if __name__ == "__main__":
    multi_turn_conversation()
    print("\n" + "="*60 + "\n")
    conversation_with_history()
