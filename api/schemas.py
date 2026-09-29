"""
NetGuard AI — Pydantic schemas (api/schemas.py)
Mirrors AGENTS.md §4 exactly. Don't rename fields without updating both.
"""

from typing import Any, Dict, List, Optional
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


# --- DB / History Schemas (api/db-history) ---


class FlowResponse(BaseModel):
    id: str
    ts: float
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    dst_port: Optional[int] = None
    label: str
    confidence: float
    features: Optional[Dict[str, float]] = None
    top_features: Optional[List[TopFeature]] = None

    model_config = {"from_attributes": True}


class FlowCreate(BaseModel):
    id: Optional[str] = None
    ts: Optional[float] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    dst_port: Optional[int] = None
    label: str
    confidence: float
    features: Optional[Dict[str, float]] = None
    top_features: Optional[List[TopFeature]] = None


class AlertResponse(BaseModel):
    id: int
    first_seen: float
    last_seen: float
    src_ip: str
    label: str
    max_confidence: float
    flow_count: int
    status: str

    model_config = {"from_attributes": True}


class AlertCreate(BaseModel):
    first_seen: Optional[float] = None
    last_seen: Optional[float] = None
    src_ip: str
    label: str
    max_confidence: float
    flow_count: int = 1
    status: str = "open"


class StatsResponse(BaseModel):
    total: int = 0
    counts: Dict[str, int] = {}
    by_label: Dict[str, int] = {}
    Benign: int = 0
    DoS_DDoS: int = 0
    PortScan: int = 0
    BruteForce: int = 0
    window_seconds: Optional[float] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


# --- Ingest schemas (api/ingest) ---


class IngestFlowInput(BaseModel):
    id: Optional[str] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    dst_port: Optional[int] = None
    timestamp: Optional[float] = None
    features: Dict[str, float]


class IngestRequest(BaseModel):
    flows: List[IngestFlowInput]


class IngestFlowResult(BaseModel):
    id: str
    label: str
    confidence: float
    top_features: List[TopFeature]
    alert_triggered: bool
    alert_id: Optional[int] = None


class IngestResponse(BaseModel):
    results: List[IngestFlowResult]