"""Phoenix tracing configuration for observability and debugging."""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from openinference.instrumentation import using_session
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import trace as trace_api
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor


def setup_phoenix_tracing(
    phoenix_endpoint: Optional[str] = None,
    console_export: bool = False,
) -> None:
    """Set up Phoenix tracing for LangChain operations.

    Args:
        phoenix_endpoint: Phoenix collector endpoint URL.
                         Defaults to http://localhost:6006/v1/traces
        console_export: If True, also export traces to console for debugging

    Environment Variables:
        PHOENIX_ENDPOINT: Override default Phoenix endpoint
        PHOENIX_ENABLED: Set to "false" to disable tracing
        PHOENIX_CONSOLE_EXPORT: Set to "true" to enable console export
    """
    # Check if tracing is enabled
    if os.getenv("PHOENIX_ENABLED", "true").lower() == "false":
        print("Phoenix tracing is disabled")
        return

    # Get Phoenix endpoint from env or parameter
    endpoint = phoenix_endpoint or os.getenv(
        "PHOENIX_ENDPOINT", "http://localhost:6006/v1/traces"
    )

    # Get console export setting from env
    console_export = console_export or os.getenv("PHOENIX_CONSOLE_EXPORT", "false").lower() == "true"

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


def is_tracing_enabled() -> bool:
    """Check if Phoenix tracing is enabled.

    Returns:
        True if tracing is enabled, False otherwise
    """
    return os.getenv("PHOENIX_ENABLED", "true").lower() == "true"


@contextmanager
def trace_session(session_id: str) -> Generator[None, None, None]:
    """Context manager for tracing a session.

    Groups related traces together in Phoenix under a single session.
    This enables better visualization and analysis of multi-turn conversations.

    Args:
        session_id: Unique identifier for the session/conversation

    Yields:
        None

    Example:
        >>> with trace_session("user-session-123"):
        ...     response = model.invoke(messages)
    """
    if is_tracing_enabled():
        with using_session(session_id):
            yield
    else:
        yield
