"""Command-line interface for langchain-docker."""

import argparse
import sys


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI.

    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog="langchain-docker",
        description="LangChain Docker - Multi-provider LLM API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  langchain-docker serve
  langchain-docker serve --port 8080
  langchain-docker serve --reload --log-level debug
        """,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Command to run",
        required=True,
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
    serve_parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level (default: info)",
    )

    return parser


def run_serve_command(args: argparse.Namespace) -> None:
    """Run the FastAPI server.

    Args:
        args: Parsed command-line arguments
    """
    import logging

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed. Install with: uv add uvicorn")
        sys.exit(1)

    # Configure logging level for all loggers
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print(f"\n{'='*60}")
    print("Starting FastAPI Server")
    print(f"{'='*60}")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Reload: {args.reload}")
    print(f"Log Level: {args.log_level}")
    print(f"{'='*60}\n")
    print(f"API Documentation: http://{args.host}:{args.port}/docs")
    print(f"Health Check: http://{args.host}:{args.port}/health")
    print(f"{'='*60}\n")

    uvicorn.run(
        "langchain_docker.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    command_map = {
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
