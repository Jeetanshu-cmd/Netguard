"""Tests for flow history endpoints (api/routes/flows.py)."""

from api.db import Flow


def test_get_flow_by_id(client, db_session):
    flow = Flow(
        id="flow-test-1",
        ts=1700000000.0,
        src_ip="192.168.1.10",
        dst_ip="192.168.1.1",
        dst_port=80,
        label="Benign",
        confidence=0.98,
        features={"dst_port": 80.0, "fwd_packets": 5.0},
        top_features=[{"feature": "dst_port", "value": 80.0, "importance": 0.2}],
    )
    db_session.add(flow)
    db_session.commit()

    resp = client.get("/flows/flow-test-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "flow-test-1"
    assert data["src_ip"] == "192.168.1.10"
    assert data["dst_ip"] == "192.168.1.1"
    assert data["dst_port"] == 80
    assert data["label"] == "Benign"
    assert data["confidence"] == 0.98
    assert data["features"]["dst_port"] == 80.0
    assert len(data["top_features"]) == 1
    assert data["top_features"][0]["feature"] == "dst_port"


def test_get_flow_not_found(client):
    resp = client.get("/flows/non-existent-flow")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_get_flows_pagination(client, db_session):
    for i in range(15):
        flow = Flow(
            id=f"flow-{i:02d}",
            ts=1700000000.0 + i,
            src_ip="10.0.0.1",
            dst_ip="10.0.0.2",
            dst_port=80,
            label="Benign",
            confidence=0.9,
        )
        db_session.add(flow)
    db_session.commit()

    resp = client.get("/flows?limit=5&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    assert data[0]["id"] == "flow-14"
    assert data[4]["id"] == "flow-10"

    resp = client.get("/flows?limit=5&offset=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    assert data[0]["id"] == "flow-09"


def test_get_flows_filter_by_label(client, db_session):
    db_session.add_all([
        Flow(id="f1", ts=100.0, label="Benign", confidence=0.9),
        Flow(id="f2", ts=101.0, label="PortScan", confidence=0.95),
        Flow(id="f3", ts=102.0, label="DoS_DDoS", confidence=0.88),
    ])
    db_session.commit()

    resp = client.get("/flows?label=PortScan")
    assert resp.status_code == 200
    flows = resp.json()
    assert len(flows) == 1
    assert flows[0]["id"] == "f2"
    assert flows[0]["label"] == "PortScan"


def test_get_flows_filter_by_ip(client, db_session):
    db_session.add_all([
        Flow(id="f1", ts=100.0, src_ip="192.168.1.10", dst_ip="10.0.0.1", label="Benign", confidence=0.9),
        Flow(id="f2", ts=101.0, src_ip="192.168.1.20", dst_ip="10.0.0.1", label="BruteForce", confidence=0.95),
        Flow(id="f3", ts=102.0, src_ip="192.168.1.10", dst_ip="10.0.0.2", label="Benign", confidence=0.92),
    ])
    db_session.commit()

    resp = client.get("/flows?src_ip=192.168.1.10")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = client.get("/flows?dst_ip=10.0.0.2")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == "f3"


def test_get_flows_filter_by_time_range(client, db_session):
    db_session.add_all([
        Flow(id="f1", ts=100.0, label="Benign", confidence=0.9),
        Flow(id="f2", ts=200.0, label="PortScan", confidence=0.9),
        Flow(id="f3", ts=300.0, label="DoS_DDoS", confidence=0.9),
    ])
    db_session.commit()

    resp = client.get("/flows?from=150&to=250")
    assert resp.status_code == 200
    flows = resp.json()
    assert len(flows) == 1
    assert flows[0]["id"] == "f2"

    resp = client.get("/flows?from_ts=200&to_ts=350")
    assert resp.status_code == 200
    flows = resp.json()
    assert len(flows) == 2
    assert [f["id"] for f in flows] == ["f3", "f2"]


def test_predict_remains_pure_no_db_writes(client, db_session):
    assert db_session.query(Flow).count() == 0

    from api.tests.test_predict import SAMPLE_FEATURES
    resp = client.post("/predict", json={"features": SAMPLE_FEATURES})
    assert resp.status_code == 200

    resp = client.post("/predict/batch", json={"flows": [{"id": "batch-1", "features": SAMPLE_FEATURES}]})
    assert resp.status_code == 200

    assert db_session.query(Flow).count() == 0
