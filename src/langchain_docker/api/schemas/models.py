"""Model-related Pydantic schemas."""

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    """Information about a specific model."""

    name: str
    description: str


class ProviderInfo(BaseModel):
    """Information about a model provider."""

    name: str
    available: bool
    configured: bool = Field(..., description="Whether API key is configured")
    default_model: str


class ProviderDetails(BaseModel):
    """Detailed information about a provider."""

    name: str
    configured: bool
    available_models: list[ModelInfo]
    default_model: str


class ValidateRequest(BaseModel):
    """Request schema for validating model configuration."""

    provider: str
    model: str
    temperature: float = Field(0.0, ge=0.0, le=2.0)


class ValidateResponse(BaseModel):
    """Response schema for model validation."""

    valid: bool
    provider: str
    model: str
    message: str
    error: str | None = None
    setup_url: str | None = None
