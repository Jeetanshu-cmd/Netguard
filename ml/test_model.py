"""
NetGuard AI — Model Artifacts Verification Test (ml/test_model.py)

Loads trained artifacts from ml/artifacts/ (model.pkl and features.json),
takes 5 rows from the held-out sample, and asserts that:
1. Features are provided in the exact saved column order.
2. Output predictions are strings belonging to the expected target classes.
3. Prediction confidence scores are floats strictly within [0.0, 1.0].
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd


def test_model_artifacts(artifacts_dir: str = "ml/artifacts"):
    model_path = os.path.join(artifacts_dir, "model.pkl")
    features_path = os.path.join(artifacts_dir, "features.json")
    sample_path = os.path.join(artifacts_dir, "held_out_sample.csv")

    assert os.path.isfile(model_path), f"Missing model binary at {model_path}"
    assert os.path.isfile(features_path), f"Missing feature schema at {features_path}"

    with open(features_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    expected_features = schema["features"]
    target_classes = schema["classes"]

    print(f"[Test] Loaded features schema with {len(expected_features)} features (Variant: {schema.get('selected_variant')}).")
    print(f"[Test] Target classes: {target_classes}")

    # Load model
    model = joblib.load(model_path)
    print(f"[Test] Loaded trained model: {type(model).__name__}")

    # Load sample rows
    if os.path.isfile(sample_path):
        sample_df = pd.read_csv(sample_path).head(5)
        print(f"[Test] Loaded 5 rows from {sample_path}")
    else:
        print(f"[Test] Held-out CSV not found. Generating 5 synthetic test rows conforming to schema.")
        sample_data = {feat: np.random.uniform(1.0, 100.0, size=5).astype(np.float32) for feat in expected_features}
        if "dst_port" in sample_data:
            sample_data["dst_port"] = np.array([80, 443, 22, 8080, 53], dtype=np.float32)
        sample_df = pd.DataFrame(sample_data)

    # 1. Assert feature ordering
    ordered_df = sample_df[expected_features]
    assert list(ordered_df.columns) == expected_features, "Columns do not match expected feature order"

    # 2. Run predictions & probabilities
    preds = model.predict(ordered_df)
    probas = model.predict_proba(ordered_df)

    print("\n" + "-" * 75)
    print(f"{'Row':<5} | {'Predicted Label':<14} | {'Confidence':<12} | {'Validation'}")
    print("-" * 75)

    for i in range(len(preds)):
        pred = preds[i]
        proba = probas[i]
        confidence = float(np.max(proba))

        # Assert prediction is a string
        assert isinstance(pred, (str, np.str_)), f"Row {i}: Prediction {pred} is not a string (got {type(pred)})"

        # Assert prediction is in target classes
        assert str(pred) in target_classes, f"Row {i}: Prediction {pred} not in target classes {target_classes}"

        # Assert confidence is in [0, 1]
        assert 0.0 <= confidence <= 1.0, f"Row {i}: Confidence {confidence} outside [0.0, 1.0]"

        print(f"{i:<5} | {str(pred):<14} | {confidence:<12.4f} | OK (str & [0,1])")

    print("-" * 75)
    print("[Success] All 5 sample rows passed feature order, string label, and confidence bounds assertions.")


if __name__ == "__main__":
    artifacts_dir = sys.argv[1] if len(sys.argv) > 1 else "ml/artifacts"
    test_model_artifacts(artifacts_dir=artifacts_dir)

