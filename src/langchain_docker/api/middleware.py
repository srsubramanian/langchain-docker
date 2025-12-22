"""Error handling middleware for FastAPI."""

from fastapi import Request
from fastapi.responses import JSONResponse

from langchain_docker.utils.errors import (
    APIKeyMissingError,
    InvalidProviderError,
    ModelInitializationError,
    SessionNotFoundError,
    get_setup_url,
)


async def api_key_missing_handler(request: Request, exc: APIKeyMissingError) -> JSONResponse:
    """Handle missing API key errors.

    Args:
        request: FastAPI request
        exc: Exception instance

    Returns:
        JSON error response
    """
    return JSONResponse(
        status_code=503,
        content={
            "error": "service_unavailable",
            "message": "API key not configured",
            "provider": exc.provider,
            "setup_url": get_setup_url(exc.provider),
            "details": str(exc),
        },
    )


async def model_initialization_handler(request: Request, exc: ModelInitializationError) -> JSONResponse:
    """Handle model initialization errors.

    Args:
        request: FastAPI request
        exc: Exception instance

    Returns:
        JSON error response
    """
    return JSONResponse(
        status_code=500,
        content={
            "error": "model_initialization_failed",
            "message": f"Failed to initialize {exc.provider} model",
            "provider": exc.provider,
            "model": exc.model,
            "details": str(exc),
        },
    )


async def session_not_found_handler(request: Request, exc: SessionNotFoundError) -> JSONResponse:
    """Handle session not found errors.

    Args:
        request: FastAPI request
        exc: Exception instance

    Returns:
        JSON error response
    """
    return JSONResponse(
        status_code=404,
        content={
            "error": "session_not_found",
            "message": f"Session '{exc.session_id}' not found",
            "session_id": exc.session_id,
        },
    )


async def invalid_provider_handler(request: Request, exc: InvalidProviderError) -> JSONResponse:
    """Handle invalid provider errors.

    Args:
        request: FastAPI request
        exc: Exception instance

    Returns:
        JSON error response
    """
    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_provider",
            "message": f"Invalid provider '{exc.provider}'",
            "provider": exc.provider,
            "valid_providers": exc.valid_providers,
        },
    )


def register_exception_handlers(app):
    """Register all exception handlers with FastAPI app.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(APIKeyMissingError, api_key_missing_handler)
    app.add_exception_handler(ModelInitializationError, model_initialization_handler)
    app.add_exception_handler(SessionNotFoundError, session_not_found_handler)
    app.add_exception_handler(InvalidProviderError, invalid_provider_handler)
