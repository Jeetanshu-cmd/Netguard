"""Tests for stats endpoint (api/routes/stats.py)."""

import time

from api.db import Flow


def test_get_stats_requires_auth(client):
    resp = client.get("/stats")
    assert resp.status_code == 401


def test_get_stats_empty_db(client, auth_headers):
    resp = client.get("/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["counts"] == {"Benign": 0, "DoS_DDoS": 0, "PortScan": 0, "BruteForce": 0}
    assert data["Benign"] == 0
    assert data["DoS_DDoS"] == 0
    assert data["PortScan"] == 0
    assert data["BruteForce"] == 0


def test_get_stats_aggregated_counts(client, db_session, auth_headers):
    flows = [
        Flow(id="f1", ts=100.0, label="Benign", confidence=0.9),
        Flow(id="f2", ts=101.0, label="Benign", confidence=0.9),
        Flow(id="f3", ts=102.0, label="PortScan", confidence=0.95),
        Flow(id="f4", ts=103.0, label="DoS_DDoS", confidence=0.88),
        Flow(id="f5", ts=104.0, label="BruteForce", confidence=0.92),
    ]
    db_session.add_all(flows)
    db_session.commit()

    resp = client.get("/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["counts"]["Benign"] == 2
    assert data["counts"]["PortScan"] == 1
    assert data["counts"]["DoS_DDoS"] == 1
    assert data["counts"]["BruteForce"] == 1
    assert data["Benign"] == 2
    assert data["PortScan"] == 1
    assert data["DoS_DDoS"] == 1
    assert data["BruteForce"] == 1


def test_get_stats_with_time_window(client, db_session, auth_headers):
    now = time.time()
    flows = [
        Flow(id="old", ts=now - 5000, label="PortScan", confidence=0.9),
        Flow(id="recent-1", ts=now - 10, label="PortScan", confidence=0.9),
        Flow(id="recent-2", ts=now - 5, label="Benign", confidence=0.9),
    ]
    db_session.add_all(flows)
    db_session.commit()

    resp = client.get("/stats?window=60", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["counts"]["PortScan"] == 1
    assert data["counts"]["Benign"] == 1
    assert data["window_seconds"] == 60


def test_get_stats_with_explicit_from_to(client, db_session, auth_headers):
    flows = [
        Flow(id="f1", ts=100.0, label="Benign", confidence=0.9),
        Flow(id="f2", ts=200.0, label="DoS_DDoS", confidence=0.9),
        Flow(id="f3", ts=300.0, label="PortScan", confidence=0.9),
    ]
    db_session.add_all(flows)
    db_session.commit()

    resp = client.get("/stats?from=150&to=250", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["counts"]["DoS_DDoS"] == 1
    assert data["counts"]["Benign"] == 0