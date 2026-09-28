"""Shared pytest fixtures for api/tests."""

import json

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import RandomForestClassifier

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
def client(dummy_model_dir):
    model_service.model_dir = str(dummy_model_dir)
    with TestClient(app) as test_client:
        yield test_client
    model_service.model = None