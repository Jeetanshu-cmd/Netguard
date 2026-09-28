"""api/routes/stats.py — /stats"""

import time
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db import Flow, get_db
from api.schemas import StatsResponse

router = APIRouter(tags=["stats"])

ATTACK_CLASSES = ["Benign", "DoS_DDoS", "PortScan", "BruteForce"]


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    window: Optional[float] = Query(None, alias="window", description="Time window in seconds (e.g. 3600)"),
    window_seconds: Optional[float] = Query(None, alias="window_seconds", description="Alias for window"),
    from_ts: Optional[float] = Query(None, alias="from", description="Filter flows with ts >= from"),
    to_ts: Optional[float] = Query(None, alias="to", description="Filter flows with ts <= to"),
    from_time: Optional[float] = Query(None, alias="from_ts", description="Alternative alias for from"),
    to_time: Optional[float] = Query(None, alias="to_ts", description="Alternative alias for to"),
    db: Session = Depends(get_db),
) -> StatsResponse:
    now = time.time()
    win = window if window is not None else window_seconds
    start_time = None
    end_time = to_ts if to_ts is not None else to_time

    if win is not None:
        start_time = now - win
    elif from_ts is not None:
        start_time = from_ts
    elif from_time is not None:
        start_time = from_time

    stmt = select(Flow.label, func.count(Flow.id))
    if start_time is not None:
        stmt = stmt.where(Flow.ts >= start_time)
    if end_time is not None:
        stmt = stmt.where(Flow.ts <= end_time)

    stmt = stmt.group_by(Flow.label)
    rows = db.execute(stmt).all()

    counts = {c: 0 for c in ATTACK_CLASSES}
    for label, count in rows:
        counts[label] = count

    total = sum(counts.values())

    return StatsResponse(
        total=total,
        counts=counts,
        by_label=counts,
        Benign=counts.get("Benign", 0),
        DoS_DDoS=counts.get("DoS_DDoS", 0),
        PortScan=counts.get("PortScan", 0),
        BruteForce=counts.get("BruteForce", 0),
        window_seconds=win,
        start_time=start_time,
        end_time=end_time,
    )
