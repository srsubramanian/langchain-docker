"""Command-line interface for langchain-docker examples."""

import argparse
import sys

from langchain_docker.examples import (
    agent_basics,
    basic_invocation,
    model_customization,
    multi_provider,
    streaming,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI.

    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog="langchain-docker",
        description="LangChain Foundational Models Examples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  langchain-docker basic
  langchain-docker basic --provider anthropic
  langchain-docker customize
  langchain-docker providers
  langchain-docker agent
  langchain-docker stream
  langchain-docker all
        """,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Command to run",
        required=True,
    )

    # Basic invocation command
    basic_parser = subparsers.add_parser(
        "basic",
        help="Run basic model invocation example",
    )
    basic_parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "anthropic", "google"],
        help="Model provider (default: openai)",
    )
    basic_parser.add_argument(
        "--model",
        help="Model name (provider-specific)",
    )
    basic_parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Temperature for response generation (default: 0.0)",
    )

    # Customization command
    customize_parser = subparsers.add_parser(
        "customize",
        help="Show model customization examples",
    )
    customize_parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "anthropic", "google"],
        help="Model provider (default: openai)",
    )
    customize_parser.add_argument(
        "--model",
        help="Model name (provider-specific)",
    )

    # Multi-provider command
    subparsers.add_parser(
        "providers",
        help="Compare different model providers",
    )

    # Agent command
    agent_parser = subparsers.add_parser(
        "agent",
        help="Demonstrate agent and multi-turn conversations",
    )
    agent_parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "anthropic", "google"],
        help="Model provider (default: openai)",
    )
    agent_parser.add_argument(
        "--model",
        help="Model name (provider-specific)",
    )

    # Streaming command
    stream_parser = subparsers.add_parser(
        "stream",
        help="Show streaming output examples",
    )
    stream_parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "anthropic", "google"],
        help="Model provider (default: openai)",
    )
    stream_parser.add_argument(
        "--model",
        help="Model name (provider-specific)",
    )

    # All examples command
    subparsers.add_parser(
        "all",
        help="Run all examples in sequence",
    )

    # Serve API command
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the FastAPI server",
    )
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    return parser


def run_basic_command(args: argparse.Namespace) -> None:
    """Run the basic invocation example.

    Args:
        args: Parsed command-line arguments
    """
    kwargs = {"provider": args.provider, "temperature": args.temperature}
    if args.model:
        kwargs["model"] = args.model

    basic_invocation.basic_invoke_example(**kwargs)


def run_customize_command(args: argparse.Namespace) -> None:
    """Run the customization examples.

    Args:
        args: Parsed command-line arguments
    """
    kwargs = {"provider": args.provider}
    if args.model:
        kwargs["model"] = args.model

    model_customization.temperature_comparison(**kwargs)
    print("\n" + "="*60 + "\n")
    model_customization.parameter_showcase(**kwargs)


def run_providers_command(args: argparse.Namespace) -> None:
    """Run the multi-provider examples.

    Args:
        args: Parsed command-line arguments
    """
    multi_provider.compare_providers()
    multi_provider.provider_specific_features()


def run_agent_command(args: argparse.Namespace) -> None:
    """Run the agent examples.

    Args:
        args: Parsed command-line arguments
    """
    kwargs = {"provider": args.provider}
    if args.model:
        kwargs["model"] = args.model

    agent_basics.multi_turn_conversation(**kwargs)
    print("\n" + "="*60 + "\n")
    agent_basics.conversation_with_history()


def run_stream_command(args: argparse.Namespace) -> None:
    """Run the streaming examples.

    Args:
        args: Parsed command-line arguments
    """
    kwargs = {"provider": args.provider}
    if args.model:
        kwargs["model"] = args.model

    streaming.basic_streaming(**kwargs)
    print("\n" + "="*60 + "\n")
    streaming.streaming_with_messages(**kwargs)
    print("\n" + "="*60 + "\n")
    streaming.compare_streaming_vs_invoke(**kwargs)


def run_serve_command(args: argparse.Namespace) -> None:
    """Run the FastAPI server.

    Args:
        args: Parsed command-line arguments
    """
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed. Install with: uv add uvicorn")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("Starting FastAPI Server")
    print(f"{'='*60}")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Reload: {args.reload}")
    print(f"{'='*60}\n")
    print(f"API Documentation: http://{args.host}:{args.port}/docs")
    print(f"Health Check: http://{args.host}:{args.port}/health")
    print(f"{'='*60}\n")

    uvicorn.run(
        "langchain_docker.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def run_all_command(args: argparse.Namespace) -> None:
    """Run all examples in sequence.

    Args:
        args: Parsed command-line arguments
    """
    print("\n" + "="*60)
    print("Running All Examples")
    print("="*60 + "\n")

    examples = [
        ("Basic Invocation", lambda: basic_invocation.basic_invoke_example()),
        ("Model Customization", lambda: (
            model_customization.temperature_comparison(),
            print("\n" + "="*60 + "\n"),
            model_customization.parameter_showcase(),
        )),
        ("Multi-Provider", lambda: (
            multi_provider.compare_providers(),
            multi_provider.provider_specific_features(),
        )),
        ("Agent Basics", lambda: (
            agent_basics.multi_turn_conversation(),
            print("\n" + "="*60 + "\n"),
            agent_basics.conversation_with_history(),
        )),
        ("Streaming", lambda: (
            streaming.basic_streaming(),
            print("\n" + "="*60 + "\n"),
            streaming.streaming_with_messages(),
            print("\n" + "="*60 + "\n"),
            streaming.compare_streaming_vs_invoke(),
        )),
    ]

    for i, (name, example_func) in enumerate(examples, 1):
        print(f"\n{'='*60}")
        print(f"Example {i}/{len(examples)}: {name}")
        print(f"{'='*60}\n")

        try:
            example_func()
        except Exception as e:
            print(f"\n❌ Error in {name}: {str(e)}")
            print("Continuing with next example...\n")

        if i < len(examples):
            print("\n" + "="*60)
            input("Press Enter to continue to next example...")

    print("\n" + "="*60)
    print("All Examples Complete!")
    print("="*60 + "\n")


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    command_map = {
        "basic": run_basic_command,
        "customize": run_customize_command,
        "providers": run_providers_command,
        "agent": run_agent_command,
        "stream": run_stream_command,
        "all": run_all_command,
        "serve": run_serve_command,
    }

    try:
        command_func = command_map.get(args.command)
        if command_func:
            command_func(args)
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
