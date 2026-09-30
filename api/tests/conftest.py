"""Shared pytest fixtures for api/tests."""

import json

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import RandomForestClassifier
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.db import Base, get_db
from api.inference import model_service
from api.main import app

FEATURES = [
    "dst_port", "flow_duration_s", "fwd_packets", "bwd_packets",
    "fwd_bytes", "bwd_bytes", "bytes_per_sec", "packets_per_sec",
    "pkt_len_mean", "pkt_len_std", "pkt_len_max", "pkt_len_min",
    "syn_count", "ack_count", "fin_count", "rst_count", "psh_count",
    "iat_mean", "iat_max",
]
CLASSES = ["Benign", "BruteForce", "DoS_DDoS", "PortScan"]


@pytest.fixture
def dummy_model_dir(tmp_path):
    rng = np.random.default_rng(42)
    X = rng.random((200, len(FEATURES)))
    y = rng.choice(CLASSES, size=200)
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)
    joblib.dump(model, tmp_path / "model.pkl")
    with open(tmp_path / "features.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "features": FEATURES,
                "features_count": len(FEATURES),
                "classes": CLASSES,
                "alert_threshold": 0.85,
            },
            f,
        )
    return tmp_path


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_netguard.db"
    test_db_url = f"sqlite:///{db_file}"
    test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    yield test_engine, TestingSessionLocal
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture
def db_session(test_db):
    _, TestingSessionLocal = test_db
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(dummy_model_dir, test_db):
    model_service.model_dir = str(dummy_model_dir)
    _, TestingSessionLocal = test_db

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    model_service.model = None


from api.db import User
from api.security import hash_password

@pytest.fixture
def seeded_user(db_session):
    user = User(username="admin", password_hash=hash_password("testpass123"), role="admin")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def auth_headers(client, seeded_user):
    resp = client.post("/auth/login", json={"username": "admin", "password": "testpass123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}