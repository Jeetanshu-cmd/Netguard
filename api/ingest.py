"""
NetGuard AI — Sensor ingest endpoint (api/ingest.py)

POST /ingest/flows is the ONE endpoint capture/ calls in production. Unlike
/predict (pure, no side effects), this route:
  1. classifies each flow using the same model_service as /predict,
  2. stores it as a Flow row,
  3. runs it through the alert engine (create/update/ignore),
  4. broadcasts the flow — and the alert, if one was raised — over
     /ws/flows so the dashboard updates live.

Protected by a static API key (X-API-Key header), separate from the
dashboard's future JWT login. This is a temporary, minimal check — once
api/auth exists, this dependency can move into a shared api/security.py
alongside the JWT logic, but the header name and behavior won't change.
"""

import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from api.alert_engine import process_flow_result
from api.config import settings
from api.db import Flow, get_db
from api.inference import MissingFeaturesError, ModelNotLoadedError, model_service
from api.schemas import IngestFlowResult, IngestRequest, IngestResponse, TopFeature
from api.ws import manager


def require_sensor_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    """
    Minimal shared-secret check for the sensor. Not JWT — the sensor isn't
    a logged-in user, it's a trusted service with one static key set via
    SENSOR_API_KEY in .env. Every request to this router needs it.
    """
    if not x_api_key or x_api_key != settings.sensor_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key",
        )


router = APIRouter(tags=["ingest"], dependencies=[Depends(require_sensor_api_key)])


@router.post("/ingest/flows", response_model=IngestResponse)
async def ingest_flows(request: IngestRequest, db: Session = Depends(get_db)) -> IngestResponse:
    if not request.flows:
        return IngestResponse(results=[])

    results = []

    for flow_in in request.flows:
        try:
            label, confidence, top = model_service.predict_one(flow_in.features)
        except MissingFeaturesError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ModelNotLoadedError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        ts = flow_in.timestamp if flow_in.timestamp is not None else time.time()
        dst_port = flow_in.dst_port
        if dst_port is None and "dst_port" in flow_in.features:
            dst_port = int(flow_in.features["dst_port"])

        flow_kwargs = dict(
            ts=ts,
            src_ip=flow_in.src_ip,
            dst_ip=flow_in.dst_ip,
            dst_port=dst_port,
            label=label,
            confidence=confidence,
            features=flow_in.features,
            top_features=top,
        )

        if flow_in.id:
            flow_kwargs["id"] = flow_in.id

        flow_row = Flow(**flow_kwargs)

        db.add(flow_row)
        db.commit()
        db.refresh(flow_row)

        await manager.broadcast_flow(
            {
                "id": flow_row.id,
                "src_ip": flow_row.src_ip,
                "dst_ip": flow_row.dst_ip,
                "label": flow_row.label,
                "confidence": flow_row.confidence,
                "timestamp": flow_row.ts,
            }
        )

        outcome = process_flow_result(
            db,
            src_ip=flow_in.src_ip,
            label=label,
            confidence=confidence,
            timestamp=ts,
            threshold=model_service.alert_threshold,
        )

        alert_id = None
        if outcome.alert is not None:
            alert_id = outcome.alert.id
            await manager.broadcast_alert(
                {
                    "id": outcome.alert.id,
                    "src_ip": outcome.alert.src_ip,
                    "label": outcome.alert.label,
                    "confidence": outcome.alert.max_confidence,
                    "flow_count": outcome.alert.flow_count,
                    "status": outcome.alert.status,
                    "timestamp": outcome.alert.last_seen,
                    "new": outcome.created,
                }
            )

        results.append(
            IngestFlowResult(
                id=flow_row.id,
                label=label,
                confidence=confidence,
                top_features=[TopFeature(**f) for f in top],
                alert_triggered=outcome.alert is not None,
                alert_id=alert_id,
            )
        )

    return IngestResponse(results=results)