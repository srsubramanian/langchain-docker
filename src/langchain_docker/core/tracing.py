"""Tracing configuration for LLM observability.

Supports multiple tracing platforms:
- LangSmith: Hosted solution with tight LangChain integration
- Phoenix: Open source, self-hosted, framework agnostic
"""

import os
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, Optional, TypeVar

# Global state for tracing
_tracing_provider: Optional[str] = None
_tracing_initialized: bool = False

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


def setup_tracing(provider: Optional[str] = None) -> None:
    """Set up tracing for LLM operations.

    Args:
        provider: Tracing provider ("langsmith", "phoenix", or "none").
                  If not specified, reads from TRACING_PROVIDER env var.

    Environment Variables:
        TRACING_PROVIDER: Choose tracing platform (langsmith, phoenix, none)

        For LangSmith:
            LANGCHAIN_API_KEY: LangSmith API key
            LANGCHAIN_PROJECT: Project name (optional)
            LANGCHAIN_ENDPOINT: API endpoint (optional)

        For Phoenix:
            PHOENIX_ENDPOINT: Phoenix collector endpoint
            PHOENIX_CONSOLE_EXPORT: Export traces to console (optional)
    """
    global _tracing_provider, _tracing_initialized

    if _tracing_initialized:
        return

    # Determine provider
    provider = provider or os.getenv("TRACING_PROVIDER", "phoenix").lower()
    _tracing_provider = provider

    if provider == "langsmith":
        _setup_langsmith()
    elif provider == "phoenix":
        _setup_phoenix()
    elif provider == "none":
        print("Tracing is disabled")
    else:
        print(f"Unknown tracing provider: {provider}. Tracing disabled.")
        _tracing_provider = "none"

    _tracing_initialized = True


def _setup_langsmith() -> None:
    """Set up LangSmith tracing.

    LangSmith uses environment variables for configuration.
    LangChain automatically enables tracing when LANGCHAIN_TRACING_V2=true.
    """
    api_key = os.getenv("LANGCHAIN_API_KEY")

    if not api_key:
        print("Warning: LANGCHAIN_API_KEY not set. LangSmith tracing disabled.")
        return

    # Enable LangSmith tracing via environment variables
    os.environ["LANGCHAIN_TRACING_V2"] = "true"

    # Set project name if provided
    project = os.getenv("LANGCHAIN_PROJECT", "langchain-docker")
    os.environ["LANGCHAIN_PROJECT"] = project

    # Set endpoint if provided (defaults to https://api.smith.langchain.com)
    endpoint = os.getenv("LANGCHAIN_ENDPOINT")
    if endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint

    print(f"✓ LangSmith tracing enabled: project={project}")
    print(f"  View traces at: https://smith.langchain.com/project/{project}")


def _setup_phoenix() -> None:
    """Set up Phoenix tracing using OpenTelemetry."""
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from opentelemetry import trace as trace_api
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk import trace as trace_sdk
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

    # Get Phoenix endpoint from env
    endpoint = os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006/v1/traces")

    # Get console export setting
    console_export = os.getenv("PHOENIX_CONSOLE_EXPORT", "false").lower() == "true"

    try:
        # Set up tracer provider
        tracer_provider = trace_sdk.TracerProvider()
        trace_api.set_tracer_provider(tracer_provider)

        # Add OTLP exporter for Phoenix
        otlp_exporter = OTLPSpanExporter(endpoint=endpoint)
        tracer_provider.add_span_processor(SimpleSpanProcessor(otlp_exporter))

        # Optionally add console exporter for debugging
        if console_export:
            console_exporter = ConsoleSpanExporter()
            tracer_provider.add_span_processor(SimpleSpanProcessor(console_exporter))

        # Instrument LangChain
        LangChainInstrumentor().instrument()

        print(f"✓ Phoenix tracing enabled: {endpoint}")

    except Exception as e:
        print(f"Warning: Failed to initialize Phoenix tracing: {e}")
        print("Application will continue without tracing")


def get_tracing_provider() -> Optional[str]:
    """Get the current tracing provider.

    Returns:
        The tracing provider name or None if not initialized
    """
    return _tracing_provider


def is_tracing_enabled() -> bool:
    """Check if tracing is enabled.

    Returns:
        True if tracing is enabled, False otherwise
    """
    return _tracing_provider is not None and _tracing_provider != "none"


@contextmanager
def trace_session(session_id: str) -> Generator[None, None, None]:
    """Context manager for tracing a session.

    Groups related traces together under a single session.
    This enables better visualization and analysis of multi-turn conversations.

    For LangSmith: Sets session_id in run metadata via trace context
    For Phoenix: Uses OpenInference session context

    Args:
        session_id: Unique identifier for the session/conversation

    Yields:
        None

    Example:
        >>> with trace_session("user-session-123"):
        ...     response = model.invoke(messages)
    """
    if not is_tracing_enabled():
        yield
        return

    if _tracing_provider == "langsmith":
        try:
            from langsmith.run_helpers import trace

            # Use LangSmith's trace context manager to set session metadata
            with trace(
                name="session",
                run_type="chain",
                metadata={"session_id": session_id},
                tags=["session"],
            ):
                yield
        except ImportError:
            yield

    elif _tracing_provider == "phoenix":
        # Phoenix uses OpenInference session context
        from openinference.instrumentation import using_session

        with using_session(session_id=session_id):
            yield

    else:
        yield


def traceable(
    name: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
    run_type: str = "chain",
) -> Callable[[F], F]:
    """Decorator to trace a function.

    For LangSmith: Uses @traceable decorator from langsmith
    For Phoenix: Uses OpenTelemetry spans
    For none: No-op passthrough

    Note: This decorator checks the tracing provider at RUNTIME, not decoration time.
    This allows decorators to be applied before setup_tracing() is called.

    Args:
        name: Optional name for the trace (defaults to function name)
        metadata: Optional metadata dict to attach to trace
        tags: Optional list of tags
        run_type: Type of run for LangSmith (chain, llm, tool, etc.)

    Returns:
        Decorated function

    Example:
        >>> @traceable(name="process_chat", tags=["chat"])
        ... def process_message(message: str) -> str:
        ...     return llm.invoke(message)
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check tracing status at runtime
            if not is_tracing_enabled():
                return func(*args, **kwargs)

            provider = get_tracing_provider()

            if provider == "langsmith":
                try:
                    from langsmith.run_helpers import trace

                    # Use trace context manager for runtime tracing
                    with trace(
                        name=name or func.__name__,
                        run_type=run_type,
                        metadata=metadata,
                        tags=tags,
                    ):
                        return func(*args, **kwargs)
                except ImportError:
                    return func(*args, **kwargs)

            elif provider == "phoenix":
                from opentelemetry import trace as trace_api

                tracer = trace_api.get_tracer(__name__)
                span_name = name or func.__name__

                with tracer.start_as_current_span(span_name) as span:
                    if metadata:
                        for key, value in metadata.items():
                            span.set_attribute(f"metadata.{key}", str(value))
                    if tags:
                        span.set_attribute("tags", ",".join(tags))
                    return func(*args, **kwargs)

            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def get_langsmith_extra(
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """Get langsmith_extra dict for passing to @traceable functions.

    This is used to pass dynamic metadata to LangSmith traces at runtime.

    Args:
        session_id: Session ID for grouping traces
        metadata: Additional metadata
        tags: Additional tags

    Returns:
        Dict to pass as langsmith_extra parameter

    Example:
        >>> @traceable()
        ... def my_func(x, langsmith_extra=None):
        ...     pass
        >>> my_func(x, langsmith_extra=get_langsmith_extra(session_id="123"))
    """
    extra: dict = {}

    if _tracing_provider == "langsmith":
        if metadata or session_id:
            extra["metadata"] = metadata or {}
            if session_id:
                extra["metadata"]["session_id"] = session_id
        if tags:
            extra["tags"] = tags

    return extra
