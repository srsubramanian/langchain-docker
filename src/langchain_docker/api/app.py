"""FastAPI application factory."""

from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from langchain_docker.api.middleware import register_exception_handlers
from langchain_docker.api.routers import agents, chat, models, sessions
from langchain_docker.core.config import load_environment
from langchain_docker.core.tracing import setup_tracing

# Load environment variables
load_environment()

# Initialize tracing (LangSmith or Phoenix based on TRACING_PROVIDER env var)
setup_tracing()


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="LangChain Docker API",
        description="REST API for LangChain foundational models with chat, model management, and session support",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware for Chainlit and other frontends
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://localhost:8001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    register_exception_handlers(app)

    # Register routers with /api/v1 prefix
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(models.router, prefix="/api/v1")
    app.include_router(sessions.router, prefix="/api/v1")
    app.include_router(agents.router, prefix="/api/v1")

    # Health check endpoint
    @app.get("/health")
    def health_check():
        """Health check endpoint.

        Returns:
            Health status
        """
        return {
            "status": "healthy",
            "version": "0.1.0",
            "timestamp": datetime.utcnow().isoformat(),
        }

    # Detailed status endpoint
    @app.get("/api/v1/status")
    def get_status():
        """Get API status including provider configuration.

        Returns:
            Detailed status information
        """
        from langchain_docker.api.dependencies import get_model_service, get_session_service
        from langchain_docker.core.tracing import get_tracing_provider

        model_service = get_model_service()
        session_service = get_session_service()

        providers = {}
        for provider_info in model_service.list_providers():
            providers[provider_info.name] = (
                "configured" if provider_info.configured else "not_configured"
            )

        return {
            "api_version": "v1",
            "providers": providers,
            "active_sessions": len(session_service._sessions),
            "cached_models": model_service.get_cache_size(),
            "tracing_provider": get_tracing_provider() or "none",
        }

    return app


# Create app instance for uvicorn
app = create_app()
