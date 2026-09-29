"""
Tests for api/alert_engine.py — threshold gating and de-duplication.

Uses the `db_session` fixture from conftest.py (a real SQLite session
backed by a temp file, created fresh per test) so these exercise the
actual SQLAlchemy Alert model, not a mock.
"""

from sqlalchemy import select

from api.alert_engine import process_flow_result
from api.db import Alert

THRESHOLD = 0.85


def count_alerts(db_session) -> int:
    return len(db_session.scalars(select(Alert)).all())


def test_benign_never_raises_an_alert(db_session):
    outcome = process_flow_result(
        db_session, src_ip="10.0.0.5", label="Benign", confidence=0.99,
        timestamp=1000.0, threshold=THRESHOLD,
    )
    assert outcome.alert is None
    assert outcome.created is False
    assert count_alerts(db_session) == 0


def test_confidence_below_threshold_is_ignored(db_session):
    outcome = process_flow_result(
        db_session, src_ip="10.0.0.5", label="PortScan", confidence=0.50,
        timestamp=1000.0, threshold=THRESHOLD,
    )
    assert outcome.alert is None
    assert count_alerts(db_session) == 0


def test_confidence_exactly_at_threshold_is_ignored(db_session):
    # Rule is "strictly greater than" (confidence > threshold), so a tie
    # does NOT trigger — this pins that boundary down explicitly.
    outcome = process_flow_result(
        db_session, src_ip="10.0.0.5", label="PortScan", confidence=THRESHOLD,
        timestamp=1000.0, threshold=THRESHOLD,
    )
    assert outcome.alert is None
    assert count_alerts(db_session) == 0


def test_no_src_ip_is_ignored(db_session):
    outcome = process_flow_result(
        db_session, src_ip=None, label="DoS_DDoS", confidence=0.95,
        timestamp=1000.0, threshold=THRESHOLD,
    )
    assert outcome.alert is None
    assert count_alerts(db_session) == 0


def test_first_qualifying_flow_creates_a_new_alert(db_session):
    outcome = process_flow_result(
        db_session, src_ip="10.0.0.5", label="PortScan", confidence=0.90,
        timestamp=1000.0, threshold=THRESHOLD,
    )
    assert outcome.created is True
    alert = outcome.alert
    assert alert is not None
    assert alert.src_ip == "10.0.0.5"
    assert alert.label == "PortScan"
    assert alert.flow_count == 1
    assert alert.max_confidence == 0.90
    assert alert.first_seen == 1000.0
    assert alert.last_seen == 1000.0
    assert alert.status == "open"
    assert count_alerts(db_session) == 1


def test_second_flow_within_window_updates_same_alert(db_session):
    first = process_flow_result(
        db_session, src_ip="10.0.0.5", label="PortScan", confidence=0.90,
        timestamp=1000.0, threshold=THRESHOLD,
    ).alert

    second = process_flow_result(
        db_session, src_ip="10.0.0.5", label="PortScan", confidence=0.92,
        timestamp=1015.0, threshold=THRESHOLD,  # 15s later, within 30s window
    )

    assert second.created is False
    assert second.alert.id == first.id          # same row, not a new one
    assert second.alert.flow_count == 2
    assert second.alert.last_seen == 1015.0
    assert second.alert.first_seen == 1000.0    # unchanged
    assert second.alert.max_confidence == 0.92
    assert count_alerts(db_session) == 1


def test_max_confidence_keeps_the_highest_seen(db_session):
    process_flow_result(
        db_session, src_ip="10.0.0.5", label="PortScan", confidence=0.97,
        timestamp=1000.0, threshold=THRESHOLD,
    )
    second = process_flow_result(
        db_session, src_ip="10.0.0.5", label="PortScan", confidence=0.90,  # lower
        timestamp=1010.0, threshold=THRESHOLD,
    )
    # A later, less-confident detection of the same attack shouldn't erase
    # the strongest evidence seen so far.
    assert second.alert.max_confidence == 0.97


def test_flow_after_dedup_window_creates_a_new_alert(db_session):
    first = process_flow_result(
        db_session, src_ip="10.0.0.5", label="PortScan", confidence=0.90,
        timestamp=1000.0, threshold=THRESHOLD,
    ).alert

    # settings.alert_dedup_seconds defaults to 30; 1000 + 31 is outside it.
    second = process_flow_result(
        db_session, src_ip="10.0.0.5", label="PortScan", confidence=0.90,
        timestamp=1031.0, threshold=THRESHOLD,
    )

    assert second.created is True
    assert second.alert.id != first.id
    assert count_alerts(db_session) == 2


def test_different_label_same_ip_creates_a_separate_alert(db_session):
    process_flow_result(
        db_session, src_ip="10.0.0.5", label="PortScan", confidence=0.90,
        timestamp=1000.0, threshold=THRESHOLD,
    )
    outcome = process_flow_result(
        db_session, src_ip="10.0.0.5", label="DoS_DDoS", confidence=0.90,
        timestamp=1005.0, threshold=THRESHOLD,
    )
    assert outcome.created is True
    assert count_alerts(db_session) == 2


def test_different_ip_same_label_creates_a_separate_alert(db_session):
    process_flow_result(
        db_session, src_ip="10.0.0.5", label="PortScan", confidence=0.90,
        timestamp=1000.0, threshold=THRESHOLD,
    )
    outcome = process_flow_result(
        db_session, src_ip="10.0.0.6", label="PortScan", confidence=0.90,
        timestamp=1005.0, threshold=THRESHOLD,
    )
    assert outcome.created is True
    assert count_alerts(db_session) == 2