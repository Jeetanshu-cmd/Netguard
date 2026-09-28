from fastapi.testclient import TestClient

from api.inference import model_service
from api.main import app
from api.tests.conftest import CLASSES, FEATURES

SAMPLE_FEATURES = {name: 1.0 for name in FEATURES}
SAMPLE_FEATURES.update({"dst_port": 80, "syn_count": 1, "ack_count": 8})


def test_predict_returns_valid_label_and_confidence(client):
    resp = client.post("/predict", json={"features": SAMPLE_FEATURES})
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] in CLASSES
    assert 0.0 <= body["confidence"] <= 1.0
    assert len(body["top_features"]) == 3
    for tf in body["top_features"]:
        assert set(tf.keys()) == {"feature", "value", "importance"}


def test_predict_missing_feature_returns_422(client):
    incomplete = dict(SAMPLE_FEATURES)
    del incomplete["syn_count"]
    resp = client.post("/predict", json={"features": incomplete})
    assert resp.status_code == 422
    assert "syn_count" in resp.json()["detail"]


def test_predict_batch_preserves_order_and_ids(client):
    payload = {
        "flows": [
            {"id": "flow-1", "src_ip": "10.0.0.1", "dst_ip": "10.0.0.2", "features": SAMPLE_FEATURES},
            {"id": "flow-2", "src_ip": "10.0.0.3", "dst_ip": "10.0.0.2", "features": SAMPLE_FEATURES},
        ]
    }
    resp = client.post("/predict/batch", json=payload)
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert [r["id"] for r in results] == ["flow-1", "flow-2"]
    assert all(r["label"] in CLASSES for r in results)


def test_predict_batch_empty_list(client):
    resp = client.post("/predict/batch", json={"flows": []})
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


def test_health_before_model_loaded_reports_degraded(dummy_model_dir):
    empty_dir = dummy_model_dir / "empty"
    empty_dir.mkdir()
    model_service.model_dir = str(empty_dir)

    with TestClient(app) as c:
        resp = c.get("/health")
        assert resp.status_code == 200
        assert resp.json()["model_loaded"] is False

    model_service.model = None