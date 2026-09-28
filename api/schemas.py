"""
NetGuard AI — Pydantic schemas (api/schemas.py)
Mirrors AGENTS.md §4 exactly. Don't rename fields without updating both.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel


class TopFeature(BaseModel):
    feature: str
    value: float
    importance: float


class PredictRequest(BaseModel):
    features: Dict[str, float]


class PredictResponse(BaseModel):
    label: str
    confidence: float
    top_features: List[TopFeature]


class BatchFlowInput(BaseModel):
    id: str
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    features: Dict[str, float]


class PredictBatchRequest(BaseModel):
    flows: List[BatchFlowInput]


class BatchFlowResult(BaseModel):
    id: str
    label: str
    confidence: float
    top_features: List[TopFeature]


class PredictBatchResponse(BaseModel):
    results: List[BatchFlowResult]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    timestamp: str


class ModelInfoResponse(BaseModel):
    model_type: str
    classes: List[str]
    features_count: int
    features: List[str]
    alert_threshold: float