"""Model management API endpoints."""

from fastapi import APIRouter, Depends

from langchain_docker.api.dependencies import get_model_service
from langchain_docker.api.schemas.models import (
    ProviderDetails,
    ProviderInfo,
    ValidateRequest,
    ValidateResponse,
)
from langchain_docker.api.services.model_service import ModelService
from langchain_docker.utils.errors import get_setup_url

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/providers", response_model=list[ProviderInfo])
def list_providers(
    model_service: ModelService = Depends(get_model_service),
):
    """List all available model providers.

    Returns:
        List of provider information including availability and configuration status
    """
    return model_service.list_providers()


@router.get("/providers/{provider}", response_model=ProviderDetails)
def get_provider_details(
    provider: str,
    model_service: ModelService = Depends(get_model_service),
):
    """Get detailed information about a specific provider.

    Args:
        provider: Provider name (openai, anthropic, google)

    Returns:
        Provider details including available models
    """
    return model_service.get_provider_details(provider)


@router.post("/validate", response_model=ValidateResponse)
def validate_model_config(
    request: ValidateRequest,
    model_service: ModelService = Depends(get_model_service),
):
    """Validate a model configuration.

    Args:
        request: Validation request with provider, model, and temperature

    Returns:
        Validation result with error details if invalid
    """
    try:
        # Try to get/create the model to validate configuration
        model_service.get_or_create(
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
        )

        return ValidateResponse(
            valid=True,
            provider=request.provider,
            model=request.model,
            message="Model configuration is valid",
        )

    except Exception as e:
        return ValidateResponse(
            valid=False,
            provider=request.provider,
            model=request.model,
            message="Model configuration is invalid",
            error=str(e),
            setup_url=get_setup_url(request.provider),
        )
