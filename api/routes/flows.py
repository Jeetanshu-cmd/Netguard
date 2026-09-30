"""api/routes/flows.py — /flows and /flows/{id}"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db import Flow, get_db
from api.schemas import FlowResponse

from api.security import get_current_user
router = APIRouter(tags=["flows"], dependencies=[Depends(get_current_user)])


@router.get("/flows", response_model=List[FlowResponse])
def get_flows(
    response: Response,
    label: Optional[str] = Query(None, description="Filter by classification label"),
    src_ip: Optional[str] = Query(None, description="Filter by source IP"),
    dst_ip: Optional[str] = Query(None, description="Filter by destination IP"),
    from_ts: Optional[float] = Query(None, alias="from", description="Filter flows with ts >= from"),
    to_ts: Optional[float] = Query(None, alias="to", description="Filter flows with ts <= to"),
    from_time: Optional[float] = Query(None, alias="from_ts", description="Alternative alias for from"),
    to_time: Optional[float] = Query(None, alias="to_ts", description="Alternative alias for to"),
    limit: int = Query(50, ge=1, le=1000, description="Max flows to return"),
    offset: int = Query(0, ge=0, description="Number of flows to skip"),
    db: Session = Depends(get_db),
) -> List[FlowResponse]:
    start = from_ts if from_ts is not None else from_time
    end = to_ts if to_ts is not None else to_time

    stmt = select(Flow)
    if label:
        stmt = stmt.where(Flow.label == label)
    if src_ip:
        stmt = stmt.where(Flow.src_ip == src_ip)
    if dst_ip:
        stmt = stmt.where(Flow.dst_ip == dst_ip)
    if start is not None:
        stmt = stmt.where(Flow.ts >= start)
    if end is not None:
        stmt = stmt.where(Flow.ts <= end)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = db.scalar(count_stmt) or 0
    response.headers["X-Total-Count"] = str(total_count)

    stmt = stmt.order_by(Flow.ts.desc(), Flow.id.desc()).offset(offset).limit(limit)
    flows = list(db.scalars(stmt).all())
    return flows


@router.get("/flows/{id}", response_model=FlowResponse)
def get_flow(id: str, db: Session = Depends(get_db)) -> FlowResponse:
    flow = db.scalar(select(Flow).where(Flow.id == id))
    if not flow:
        raise HTTPException(status_code=404, detail=f"Flow '{id}' not found")
    return flow
