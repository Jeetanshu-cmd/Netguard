"""Tests for alert endpoints (api/routes/alerts.py)."""

from api.db import Alert


def test_get_alerts_requires_auth(client):
    resp = client.get("/alerts")
    assert resp.status_code == 401


def test_get_alerts_empty(client, auth_headers):
    resp = client.get("/alerts", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_alerts_and_by_id(client, db_session, auth_headers):
    alert = Alert(
        id=1,
        first_seen=1700000000.0,
        last_seen=1700000050.0,
        src_ip="192.168.1.100",
        label="PortScan",
        max_confidence=0.97,
        flow_count=25,
        status="open",
    )
    db_session.add(alert)
    db_session.commit()

    resp = client.get("/alerts", headers=auth_headers)
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) == 1
    assert alerts[0]["id"] == 1
    assert alerts[0]["src_ip"] == "192.168.1.100"
    assert alerts[0]["label"] == "PortScan"
    assert alerts[0]["max_confidence"] == 0.97
    assert alerts[0]["flow_count"] == 25
    assert alerts[0]["status"] == "open"

    resp_single = client.get("/alerts/1", headers=auth_headers)
    assert resp_single.status_code == 200
    assert resp_single.json()["id"] == 1

    resp_404 = client.get("/alerts/999", headers=auth_headers)
    assert resp_404.status_code == 404


def test_get_alerts_filter_by_status(client, db_session, auth_headers):
    db_session.add_all([
        Alert(id=1, first_seen=100.0, last_seen=110.0, src_ip="1.1.1.1", label="PortScan", max_confidence=0.9, status="open"),
        Alert(id=2, first_seen=120.0, last_seen=130.0, src_ip="2.2.2.2", label="DoS_DDoS", max_confidence=0.95, status="resolved"),
        Alert(id=3, first_seen=140.0, last_seen=150.0, src_ip="3.3.3.3", label="BruteForce", max_confidence=0.89, status="open"),
    ])
    db_session.commit()

    resp = client.get("/alerts?status=open", headers=auth_headers)
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) == 2
    assert all(a["status"] == "open" for a in alerts)

    resp = client.get("/alerts?status=resolved", headers=auth_headers)
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) == 1
    assert alerts[0]["src_ip"] == "2.2.2.2"


def test_get_alerts_filter_by_ip_and_label(client, db_session, auth_headers):
    db_session.add_all([
        Alert(id=1, first_seen=100.0, last_seen=110.0, src_ip="1.1.1.1", label="PortScan", max_confidence=0.9, status="open"),
        Alert(id=2, first_seen=120.0, last_seen=130.0, src_ip="1.1.1.1", label="BruteForce", max_confidence=0.95, status="open"),
        Alert(id=3, first_seen=140.0, last_seen=150.0, src_ip="2.2.2.2", label="PortScan", max_confidence=0.89, status="open"),
    ])
    db_session.commit()

    resp = client.get("/alerts?src_ip=1.1.1.1", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = client.get("/alerts?label=PortScan", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2