"""api/routes/predict.py — /predict and /predict/batch"""

from fastapi import APIRouter, HTTPException
from api.inference import MissingFeaturesError, ModelNotLoadedError, model_service
from api.schemas import (
    BatchFlowResult, PredictBatchRequest, PredictBatchResponse,
    PredictRequest, PredictResponse, TopFeature,
)

router = APIRouter(tags=["predict"])


@router.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    try:
        label, confidence, top = model_service.predict_one(request.features)
    except MissingFeaturesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelNotLoadedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return PredictResponse(label=label, confidence=confidence, top_features=[TopFeature(**f) for f in top])


@router.post("/predict/batch", response_model=PredictBatchResponse)
def predict_batch(request: PredictBatchRequest) -> PredictBatchResponse:
    if not request.flows:
        return PredictBatchResponse(results=[])
    try:
        predictions = model_service.predict_batch([f.features for f in request.flows])
    except MissingFeaturesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelNotLoadedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    results = [
        BatchFlowResult(id=flow.id, label=l, confidence=c, top_features=[TopFeature(**f) for f in t])
        for flow, (l, c, t) in zip(request.flows, predictions)
    ]
    return PredictBatchResponse(results=results)