"""
NetGuard AI — Model loading & inference (api/inference.py)
"""

import json
import logging
import os
import time
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd

from api.config import settings

logger = logging.getLogger("netguard.inference")


class ModelNotLoadedError(RuntimeError):
    pass


class MissingFeaturesError(ValueError):
    def __init__(self, missing: List[str]):
        self.missing = missing
        super().__init__(f"Missing required features: {missing}")


class ModelService:
    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        self.model = None
        self.feature_names: List[str] = []
        self.classes: List[str] = []
        self.alert_threshold: float = settings.default_alert_threshold
        self.model_type: str = "unknown"
        self.loaded_at: float | None = None

    def load(self) -> None:
        model_path = os.path.join(self.model_dir, "model.pkl")
        features_path = os.path.join(self.model_dir, "features.json")

        if not os.path.isfile(model_path):
            raise FileNotFoundError(
                f"model.pkl not found at {model_path}. Run `python ml/train.py` "
                "or copy ml/artifacts/ from the ML teammate."
            )
        if not os.path.isfile(features_path):
            raise FileNotFoundError(
                f"features.json not found at {features_path}. It must be saved "
                "alongside model.pkl (AGENTS.md #5.1)."
            )

        self.model = joblib.load(model_path)
        with open(features_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        self.feature_names = schema["features"]
        self.classes = schema["classes"]
        self.alert_threshold = float(schema.get("alert_threshold", settings.default_alert_threshold))
        self.model_type = type(self.model).__name__
        self.loaded_at = time.time()
        logger.info("Loaded model=%s features=%d classes=%s", self.model_type, len(self.feature_names), self.classes)

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def _require_loaded(self) -> None:
        if not self.is_loaded:
            raise ModelNotLoadedError("Model is not loaded. Check /health and startup logs.")

    def _to_frame(self, features: Dict[str, float]) -> pd.DataFrame:
        missing = [name for name in self.feature_names if name not in features]
        if missing:
            raise MissingFeaturesError(missing)
        row = {name: features[name] for name in self.feature_names}
        return pd.DataFrame([row], columns=self.feature_names)

    def _top_features(self, features: Dict[str, float], top_n: int) -> List[dict]:
        importances = getattr(self.model, "feature_importances_", None)
        if importances is None:
            return []
        ranked = sorted(zip(self.feature_names, importances), key=lambda p: p[1], reverse=True)[:top_n]
        return [{"feature": n, "value": float(features[n]), "importance": float(i)} for n, i in ranked]

    def predict_one(self, features: Dict[str, float]) -> Tuple[str, float, List[dict]]:
        self._require_loaded()
        X = self._to_frame(features)
        proba = self.model.predict_proba(X)[0]
        best_idx = int(np.argmax(proba))
        label = str(self.model.classes_[best_idx])
        confidence = round(float(proba[best_idx]), 4)
        return label, confidence, self._top_features(features, settings.top_features_count)

    def predict_batch(self, flows: List[Dict[str, float]]) -> List[Tuple[str, float, List[dict]]]:
        self._require_loaded()
        missing_by_row: Dict[int, List[str]] = {}
        rows = []
        for i, features in enumerate(flows):
            missing = [name for name in self.feature_names if name not in features]
            if missing:
                missing_by_row[i] = missing
                rows.append({name: 0.0 for name in self.feature_names})
            else:
                rows.append({name: features[name] for name in self.feature_names})
        if missing_by_row:
            first_row, missing = next(iter(missing_by_row.items()))
            raise MissingFeaturesError([f"row {first_row}: {missing}"])

        X = pd.DataFrame(rows, columns=self.feature_names)
        proba_matrix = self.model.predict_proba(X)
        results = []
        for i, proba in enumerate(proba_matrix):
            best_idx = int(np.argmax(proba))
            label = str(self.model.classes_[best_idx])
            confidence = round(float(proba[best_idx]), 4)
            results.append((label, confidence, self._top_features(flows[i], settings.top_features_count)))
        return results


model_service = ModelService(model_dir=settings.model_dir)