"""
Tests for api/ingest.py — the sensor's write path.

model_service.predict_one is monkeypatched to a fixed return value in the
alert-triggering tests, since the dummy RandomForest fixture (trained on
random data) can't be trusted to produce a specific label/confidence on
demand — we only need to prove the ingest/alert/broadcast wiring here,
not re-test classification (that's covered in test_predict.py).
"""

from api.config import settings
from api.inference import model_service

VALID_HEADERS = {"X-API-Key": settings.sensor_api_key}

SAMPLE_FEATURES = {
    "dst_port": 22, "flow_duration_s": 1.0, "fwd_packets": 5, "bwd_packets": 5,
    "fwd_bytes": 500, "bwd_bytes": 500, "bytes_per_sec": 1000, "packets_per_sec": 10,
    "pkt_len_mean": 100, "pkt_len_std": 10, "pkt_len_max": 200, "pkt_len_min": 50,
    "syn_count": 1, "ack_count": 8, "fin_count": 1, "rst_count": 0, "psh_count": 2,
    "iat_mean": 0.1, "iat_max": 0.5,
}


def test_ingest_requires_api_key(client):
    resp = client.post("/ingest/flows", json={"flows": []})
    assert resp.status_code == 401


def test_ingest_rejects_wrong_api_key(client):
    resp = client.post(
        "/ingest/flows",
        headers={"X-API-Key": "wrong-key"},
        json={"flows": []},
    )
    assert resp.status_code == 401


def test_ingest_empty_flows_returns_empty_results(client):
    resp = client.post("/ingest/flows", headers=VALID_HEADERS, json={"flows": []})
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


def test_ingest_classifies_and_stores_flow(client):
    resp = client.post(
        "/ingest/flows",
        headers=VALID_HEADERS,
        json={"flows": [{"id": "flow-a1", "src_ip": "10.0.0.5", "dst_ip": "10.0.0.2", "features": SAMPLE_FEATURES}]},
    )
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["id"] == "flow-a1"
    assert "label" in result and "confidence" in result

    stored = client.get("/flows/flow-a1")
    assert stored.status_code == 200
    assert stored.json()["src_ip"] == "10.0.0.5"


def test_ingest_generates_id_when_omitted(client):
    resp = client.post(
        "/ingest/flows",
        headers=VALID_HEADERS,
        json={"flows": [{"src_ip": "10.0.0.9", "features": SAMPLE_FEATURES}]},
    )
    assert resp.status_code == 200
    generated_id = resp.json()["results"][0]["id"]
    assert generated_id  # non-empty, auto-generated
    stored = client.get(f"/flows/{generated_id}")
    assert stored.status_code == 200


def test_ingest_broadcasts_flow_over_websocket(client):
    with client.websocket_connect("/ws/flows") as ws:
        client.post(
            "/ingest/flows",
            headers=VALID_HEADERS,
            json={"flows": [{"id": "flow-b1", "src_ip": "10.0.0.5", "features": SAMPLE_FEATURES}]},
        )
        received = ws.receive_json()
        assert received["type"] == "flow"
        assert received["id"] == "flow-b1"


def test_ingest_creates_alert_when_confidence_exceeds_threshold(client, monkeypatch):
    monkeypatch.setattr(model_service, "predict_one", lambda features: ("PortScan", 0.95, []))

    resp = client.post(
        "/ingest/flows",
        headers=VALID_HEADERS,
        json={"flows": [{"id": "flow-c1", "src_ip": "10.0.0.7", "features": SAMPLE_FEATURES}]},
    )
    result = resp.json()["results"][0]
    assert result["alert_triggered"] is True
    assert result["alert_id"] is not None

    alerts_resp = client.get("/alerts", params={"src_ip": "10.0.0.7"})
    assert len(alerts_resp.json()) == 1
    assert alerts_resp.json()[0]["label"] == "PortScan"


def test_ingest_does_not_create_alert_when_benign(client, monkeypatch):
    monkeypatch.setattr(model_service, "predict_one", lambda features: ("Benign", 0.99, []))

    resp = client.post(
        "/ingest/flows",
        headers=VALID_HEADERS,
        json={"flows": [{"id": "flow-d1", "src_ip": "10.0.0.8", "features": SAMPLE_FEATURES}]},
    )
    result = resp.json()["results"][0]
    assert result["alert_triggered"] is False
    assert result["alert_id"] is None


def test_ingest_repeated_attack_updates_same_alert_not_a_new_one(client, monkeypatch):
    monkeypatch.setattr(model_service, "predict_one", lambda features: ("DoS_DDoS", 0.90, []))

    client.post(
        "/ingest/flows",
        headers=VALID_HEADERS,
        json={"flows": [{"id": "flow-e1", "src_ip": "10.0.0.11", "features": SAMPLE_FEATURES}]},
    )
    second = client.post(
        "/ingest/flows",
        headers=VALID_HEADERS,
        json={"flows": [{"id": "flow-e2", "src_ip": "10.0.0.11", "features": SAMPLE_FEATURES}]},
    )
    alert_id_1 = second.json()["results"][0]["alert_id"]

    alerts_resp = client.get("/alerts", params={"src_ip": "10.0.0.11"})
    body = alerts_resp.json()
    assert len(body) == 1
    assert body[0]["id"] == alert_id_1
    assert body[0]["flow_count"] == 2