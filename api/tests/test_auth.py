import pytest


def test_login_succeeds_with_correct_credentials(client, seeded_user):
    resp = client.post("/auth/login", json={"username": "admin", "password": "testpass123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "admin"
    assert body["token_type"] == "bearer"


def test_login_fails_with_wrong_password(client, seeded_user):
    resp = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_fails_for_unknown_user(client):
    resp = client.post("/auth/login", json={"username": "ghost", "password": "x"})
    assert resp.status_code == 401


def test_flows_requires_auth(client):
    resp = client.get("/flows")
    assert resp.status_code == 401


def test_flows_succeeds_with_valid_token(client, auth_headers):
    resp = client.get("/flows", headers=auth_headers)
    assert resp.status_code == 200


def test_alerts_requires_auth(client):
    resp = client.get("/alerts")
    assert resp.status_code == 401


def test_stats_requires_auth(client):
    resp = client.get("/stats")
    assert resp.status_code == 401


def test_websocket_rejects_missing_token(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/flows"):
            pass


def test_websocket_accepts_valid_token(client, auth_headers, seeded_user):
    login_resp = client.post("/auth/login", json={"username": "admin", "password": "testpass123"})
    token = login_resp.json()["access_token"]
    with client.websocket_connect(f"/ws/flows?token={token}") as ws:
        pass  # connects and closes cleanly