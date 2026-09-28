"""api/routes/alerts.py — /alerts and /alerts/{id}"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db import Alert, get_db
from api.schemas import AlertResponse

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=List[AlertResponse])
def get_alerts(
    response: Response,
    status: Optional[str] = Query(None, description="Filter by status (e.g. open, acknowledged, resolved)"),
    src_ip: Optional[str] = Query(None, description="Filter by attacker source IP"),
    label: Optional[str] = Query(None, description="Filter by attack label"),
    limit: int = Query(50, ge=1, le=1000, description="Max alerts to return"),
    offset: int = Query(0, ge=0, description="Number of alerts to skip"),
    db: Session = Depends(get_db),
) -> List[AlertResponse]:
    stmt = select(Alert)
    if status:
        stmt = stmt.where(Alert.status == status)
    if src_ip:
        stmt = stmt.where(Alert.src_ip == src_ip)
    if label:
        stmt = stmt.where(Alert.label == label)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = db.scalar(count_stmt) or 0
    response.headers["X-Total-Count"] = str(total_count)

    stmt = stmt.order_by(Alert.last_seen.desc(), Alert.id.desc()).offset(offset).limit(limit)
    alerts = list(db.scalars(stmt).all())
    return alerts


@router.get("/alerts/{id}", response_model=AlertResponse)
def get_alert(id: int, db: Session = Depends(get_db)) -> AlertResponse:
    alert = db.scalar(select(Alert).where(Alert.id == id))
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{id}' not found")
    return alert
