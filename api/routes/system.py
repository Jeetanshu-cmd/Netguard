"""api/routes/system.py — /health and /model-info"""

from datetime import datetime, timezone
from fastapi import APIRouter
from api.inference import model_service
from api.schemas import HealthResponse, ModelInfoResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="healthy" if model_service.is_loaded else "degraded",
        model_loaded=model_service.is_loaded,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


@router.get("/model-info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    return ModelInfoResponse(
        model_type=model_service.model_type,
        classes=model_service.classes,
        features_count=len(model_service.feature_names),
        features=model_service.feature_names,
        alert_threshold=model_service.alert_threshold,
    )