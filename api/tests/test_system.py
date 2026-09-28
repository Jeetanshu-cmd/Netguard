def test_health_reports_model_loaded(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["model_loaded"] is True
    assert body["timestamp"].endswith("Z")


def test_model_info_matches_contract(client):
    resp = client.get("/model-info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["features_count"] == 19
    assert body["features"][0] == "dst_port"
    assert set(body["classes"]) == {"Benign", "BruteForce", "DoS_DDoS", "PortScan"}
    assert body["alert_threshold"] == 0.85