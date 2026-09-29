"""
NetGuard AI — Alert engine (api/alert_engine.py)

Decides whether a classified flow should raise or update an alert, and
applies de-duplication so a single port scan (thousands of flows from one
source) becomes ONE alert row that grows, not thousands of rows.

This is a plain function with no HTTP route and no side effects beyond the
given DB session — /ingest/flows (a later branch) will call it after
classifying a flow. Keeping it route-free makes it trivial to unit test.
"""

import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import settings
from api.db import Alert


@dataclass
class AlertOutcome:
    """
    What happened when a flow was run through the engine.

    alert:   the Alert row that was created/updated, or None if no alert
             was raised for this flow (benign, low confidence, or no src_ip).
    created: True if a brand-new alert row was inserted, False if an
             existing open alert was updated instead. Meaningless when
             alert is None. The websocket branch will use this to decide
             whether to send a fresh "alert:triggered" event or just an
             updated count.
    """
    alert: Optional[Alert]
    created: bool


def process_flow_result(
    db: Session,
    src_ip: Optional[str],
    label: str,
    confidence: float,
    timestamp: Optional[float] = None,
    threshold: Optional[float] = None,
) -> AlertOutcome:
    """
    Runs one classified flow through the alert rules and applies the
    resulting insert/update to `db` (caller is responsible for commit
    happening — see below, we commit here since this is the one place
    that needs the row's final state, e.g. its id, right away).

    Rules (README §3 / AGENTS.md):
      1. label == "Benign"        -> no alert.
      2. confidence <= threshold  -> no alert (strictly greater triggers).
      3. src_ip is None           -> no alert (Alert.src_ip is required;
                                     a flow we can't attribute to a source
                                     isn't actionable as an alert).
      4. Otherwise: look for an OPEN alert with the same (src_ip, label)
         whose last_seen is within `settings.alert_dedup_seconds` of this
         flow's timestamp. If found, update it in place (last_seen,
         flow_count += 1, max_confidence = max(old, new)). If not found
         (or the window has passed), create a new alert.

    `threshold` lets callers override the model's own alert_threshold —
    mainly for tests. In production, pass the live model_service.alert_threshold
    explicitly from the caller (api/ingest) rather than importing it here,
    so this module has no import-time dependency on the loaded model.
    """
    if label == "Benign":
        return AlertOutcome(alert=None, created=False)

    if threshold is None:
        threshold = settings.default_alert_threshold
    if confidence <= threshold:
        return AlertOutcome(alert=None, created=False)

    if not src_ip:
        return AlertOutcome(alert=None, created=False)

    ts = timestamp if timestamp is not None else time.time()
    window = settings.alert_dedup_seconds

    existing = db.scalar(
        select(Alert)
        .where(
            Alert.src_ip == src_ip,
            Alert.label == label,
            Alert.status == "open",
        )
        .order_by(Alert.last_seen.desc())
    )

    if existing is not None and (ts - existing.last_seen) <= window:
        existing.last_seen = ts
        existing.flow_count += 1
        existing.max_confidence = max(existing.max_confidence, confidence)
        db.commit()
        db.refresh(existing)
        return AlertOutcome(alert=existing, created=False)

    new_alert = Alert(
        first_seen=ts,
        last_seen=ts,
        src_ip=src_ip,
        label=label,
        max_confidence=confidence,
        flow_count=1,
        status="open",
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)
    return AlertOutcome(alert=new_alert, created=True)