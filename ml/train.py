"""
NetGuard AI — Machine Learning Training Pipeline (ml/train.py)

================================================================================
TRACED DATA PIPELINE EXAMPLE (3 raw rows -> processed)
================================================================================

1. Raw Input Rows (from CICIDS2017 CSV):
   Row A:
     {' Destination Port': 80, ' Flow Duration': 45200, ' Total Fwd Packets': 5,
      ' Total Backward Packets': 4, 'Total Length of Fwd Packets': 350,
      ' Total Length of Bwd Packets': 1200, 'Flow Bytes/s': 34292.03,
      ' Flow Packets/s': 199.11, ' Packet Length Mean': 172.22, ' Packet Length Std': 145.3,
      ' Max Packet Length': 540, ' Min Packet Length': 54, 'SYN Flag Count': 1,
      ' ACK Flag Count': 8, 'FIN Flag Count': 1, ' RST Flag Count': 0, ' PSH Flag Count': 2,
      ' Flow IAT Mean': 5600, ' Flow IAT Max': 12000, ' Label': 'BENIGN'}
   Row B (Unidirectional probe with 0 duration resulting in Inf rate):
     {' Destination Port': 443, ' Flow Duration': 0, ' Total Fwd Packets': 1,
      ' Total Backward Packets': 0, 'Total Length of Fwd Packets': 0,
      ' Total Length of Bwd Packets': 0, 'Flow Bytes/s': Infinity,
      ' Flow Packets/s': Infinity, ' Packet Length Mean': 0.0, ' Packet Length Std': 0.0,
      ' Max Packet Length': 0, ' Min Packet Length': 0, 'SYN Flag Count': 1,
      ' ACK Flag Count': 0, 'FIN Flag Count': 0, ' RST Flag Count': 0, ' PSH Flag Count': 0,
      ' Flow IAT Mean': 0, ' Flow IAT Max': 0, ' Label': 'PortScan'}
   Row C (SSH authentication flood):
     {' Destination Port': 22, ' Flow Duration': 120000, ' Total Fwd Packets': 140,
      ' Total Backward Packets': 120, 'Total Length of Fwd Packets': 9200,
      ' Total Length of Bwd Packets': 15000, 'Flow Bytes/s': 201666.67,
      ' Flow Packets/s': 2166.67, ' Packet Length Mean': 93.07, ' Packet Length Std': 45.2,
      ' Max Packet Length': 412, ' Min Packet Length': 32, 'SYN Flag Count': 2,
      ' ACK Flag Count': 250, 'FIN Flag Count': 2, ' RST Flag Count': 0, ' PSH Flag Count': 80,
      ' Flow IAT Mean': 463.32, ' Flow IAT Max': 2500, ' Label': 'SSH-Patator'}

2. Renamed & Unit-Converted (Microseconds -> Seconds: col / 1e6):
   Row A:
     dst_port=80, flow_duration_s=0.0452, fwd_packets=5, bwd_packets=4, fwd_bytes=350,
     bwd_bytes=1200, bytes_per_sec=34292.03, packets_per_sec=199.11, pkt_len_mean=172.22,
     pkt_len_std=145.3, pkt_len_max=540, pkt_len_min=54, syn_count=1, ack_count=8,
     fin_count=1, rst_count=0, psh_count=2, iat_mean=0.0056, iat_max=0.0120, label='BENIGN'
   Row B:
     dst_port=443, flow_duration_s=0.0, ..., bytes_per_sec=inf, packets_per_sec=inf, label='PortScan'
   Row C:
     dst_port=22, flow_duration_s=0.120, ..., iat_mean=0.000463, iat_max=0.0025, label='SSH-Patator'

3. Cleaned (Inf -> NaN -> Drop NaNs & Duplicates):
   Row B contains 'inf' -> converted to NaN -> dropped.
   Duplicate rows removed. Remaining: Row A, Row C.

4. Mapped & Encoded Labels:
   Row A: 'BENIGN' -> 'Benign'
   Row C: 'SSH-Patator' -> 'BruteForce'

================================================================================
TIME COMPLEXITY ANALYSIS
================================================================================
- Training Complexity:
    O(T * K * N * log(N))
    where:
      T = 150 (number of trees, n_estimators)
      N = number of training rows (at most 4 classes * 150,000 * 0.8 = 480,000 rows)
      K = sqrt(M) features evaluated per split (M = 19 or 18 => K ~ 4)
- Single Flow Prediction Complexity:
    O(T * d)
    where:
      T = 150 trees
      d = tree depth (typically <= 25-30)
    Total operations per inference: ~3,750 simple float comparisons (< 1 millisecond on modern CPU).
"""

import os
import glob
import json
import argparse
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------------
# CONTRACT SPECIFICATION & MAPPINGS (AGENTS.md)
# -----------------------------------------------------------------------------

ORDERED_FEATURES: List[str] = [
    "dst_port",
    "flow_duration_s",
    "fwd_packets",
    "bwd_packets",
    "fwd_bytes",
    "bwd_bytes",
    "bytes_per_sec",
    "packets_per_sec",
    "pkt_len_mean",
    "pkt_len_std",
    "pkt_len_max",
    "pkt_len_min",
    "syn_count",
    "ack_count",
    "fin_count",
    "rst_count",
    "psh_count",
    "iat_mean",
    "iat_max",
]

# Mapping: Stripped CICIDS2017 column name -> NetGuard feature name
CICIDS_COLUMN_MAPPING: Dict[str, str] = {
    "Destination Port": "dst_port",
    "Flow Duration": "flow_duration_s",
    "Total Fwd Packets": "fwd_packets",
    "Total Backward Packets": "bwd_packets",
    "Total Length of Fwd Packets": "fwd_bytes",
    "Total Length of Bwd Packets": "bwd_bytes",
    "Flow Bytes/s": "bytes_per_sec",
    "Flow Packets/s": "packets_per_sec",
    "Packet Length Mean": "pkt_len_mean",
    "Packet Length Std": "pkt_len_std",
    "Max Packet Length": "pkt_len_max",
    "Min Packet Length": "pkt_len_min",
    "SYN Flag Count": "syn_count",
    "ACK Flag Count": "ack_count",
    "FIN Flag Count": "fin_count",
    "RST Flag Count": "rst_count",
    "PSH Flag Count": "psh_count",
    "Flow IAT Mean": "iat_mean",
    "Flow IAT Max": "iat_max",
}

# Features that must be converted from microseconds to seconds (col / 1e6)
MICROSECOND_FEATURES: List[str] = [
    "flow_duration_s",
    "iat_mean",
    "iat_max",
]

# Strict Class Label Mapping
LABEL_MAPPING: Dict[str, str] = {
    "BENIGN": "Benign",
    "DoS Hulk": "DoS_DDoS",
    "DoS GoldenEye": "DoS_DDoS",
    "DoS slowloris": "DoS_DDoS",
    "DoS Slowhttptest": "DoS_DDoS",
    "DDoS": "DoS_DDoS",
    "PortScan": "PortScan",
    "FTP-Patator": "BruteForce",
    "SSH-Patator": "BruteForce",
}

TARGET_CLASSES: List[str] = ["Benign", "BruteForce", "DoS_DDoS", "PortScan"]
MAX_ROWS_PER_CLASS: int = 150_000
ALERT_THRESHOLD: float = 0.85


# -----------------------------------------------------------------------------
# PIPELINE STAGES
# -----------------------------------------------------------------------------

def load_raw_data(data_dir: str, sample_max_rows: int = None) -> pd.DataFrame:
    """
    Finds and loads all CICIDS2017 CSVs in data_dir, reading only required columns
    with float32 precision and encoding='latin-1'.
    """
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    print(f"[Stage 1] Found {len(csv_files)} CSV files in {data_dir}")

    chunks = []
    total_loaded = 0

    for filepath in sorted(csv_files):
        fname = os.path.basename(filepath)
        # Inspect header of the file
        sample_df = pd.read_csv(filepath, nrows=0, encoding="latin-1")
        stripped_cols = {col: col.strip() for col in sample_df.columns}

        # Check required columns
        needed_stripped = set(CICIDS_COLUMN_MAPPING.keys()) | {"Label"}
        available_stripped = set(stripped_cols.values())

        missing = needed_stripped - available_stripped
        if missing:
            raise KeyError(f"File {fname} is missing required columns: {sorted(list(missing))}")

        # Invert to map: stripped -> original column name in CSV
        col_to_raw = {stripped: raw for raw, stripped in stripped_cols.items()}
        use_raw_cols = [col_to_raw[s] for s in needed_stripped]

        # Explicit dtypes (features as float32, label as object)
        dtypes = {col_to_raw[s]: np.float32 for s in CICIDS_COLUMN_MAPPING.keys()}
        dtypes[col_to_raw["Label"]] = object

        df_chunk = pd.read_csv(
            filepath,
            usecols=use_raw_cols,
            dtype=dtypes,
            encoding="latin-1",
            nrows=sample_max_rows,
        )

        # Rename to stripped names
        df_chunk = df_chunk.rename(columns=stripped_cols)
        chunks.append(df_chunk)
        total_loaded += len(df_chunk)
        print(f"  - Loaded {len(df_chunk):>10,d} rows from {fname}")

    df = pd.concat(chunks, ignore_index=True)
    print(f"[Stage 1 Done] Total raw rows loaded: {len(df):,d}")
    return df


def map_and_convert(df: pd.DataFrame) -> pd.DataFrame:
    """
    Maps CICIDS column names to standardized feature names and converts
    microseconds to seconds for duration and inter-arrival times.
    """
    # Verify all mapping keys are present
    missing = [c for c in CICIDS_COLUMN_MAPPING.keys() if c not in df.columns]
    if missing:
        raise KeyError(f"Cannot map features. Missing columns: {missing}")

    df = df.rename(columns=CICIDS_COLUMN_MAPPING)
    df = df.rename(columns={"Label": "label"})

    # Apply microsecond to second conversion
    for feat in MICROSECOND_FEATURES:
        df[feat] = df[feat] / 1_000_000.0

    print(f"[Stage 2 Done] Columns mapped to 19 features. Units converted (us -> s).")
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replaces inf with NaN, drops NaN rows, and removes exact duplicate rows.
    Prints row counts after each step.
    """
    initial_count = len(df)
    print(f"[Stage 3] Starting data cleaning on {initial_count:,d} rows...")

    # Replace inf and -inf with NaN
    df = df.replace([np.inf, -np.inf], np.nan)

    # Drop NaNs
    df = df.dropna()
    post_nan_count = len(df)
    print(f"  - Rows after dropping NaNs / Infs: {post_nan_count:,d} (dropped {initial_count - post_nan_count:,d})")

    # Drop duplicate rows
    df = df.drop_duplicates()
    post_dup_count = len(df)
    print(f"  - Rows after dropping exact duplicates: {post_dup_count:,d} (dropped {post_nan_count - post_dup_count:,d})")

    return df


def filter_and_sample_labels(df: pd.DataFrame, max_per_class: int = MAX_ROWS_PER_CLASS) -> pd.DataFrame:
    """
    Maps raw attack labels to the 4 target classes and drops unmapped rows.
    Caps each class at max_per_class rows (seed 42).
    """
    print("[Stage 4] Mapping attack classes...")
    df["label"] = df["label"].map(LABEL_MAPPING)
    
    # Drop rows that were not mapped (e.g. Bot, Infiltration, etc.)
    df = df.dropna(subset=["label"])
    print("  - Class counts after mapping and filtering:")
    for cls_name, count in df["label"].value_counts().items():
        print(f"      * {cls_name:<12}: {count:>10,d}")

    # Cap each class
    print(f"[Stage 5] Capping each class at {max_per_class:,d} rows (random_state=42)...")
    sampled_groups = []
    for cls_name, group in df.groupby("label"):
        if len(group) > max_per_class:
            sampled = group.sample(n=max_per_class, random_state=42)
        else:
            sampled = group
        sampled_groups.append(sampled)

    df_capped = pd.concat(sampled_groups, ignore_index=True)
    df_capped = df_capped.sample(frac=1.0, random_state=42).reset_index(drop=True)

    print("  - Final class counts for training:")
    for cls_name, count in df_capped["label"].value_counts().items():
        print(f"      * {cls_name:<12}: {count:>10,d}")
    print(f"  - Total dataset size: {len(df_capped):,d} rows")
    return df_capped


def train_and_evaluate(df: pd.DataFrame, artifacts_dir: str):
    """
    Splits data (80/20 stratified), trains two Random Forest variants
    (with dst_port vs without dst_port), compares macro-F1, and saves artifacts.
    """
    os.makedirs(artifacts_dir, exist_ok=True)

    features_with_port = ORDERED_FEATURES
    features_without_port = [f for f in ORDERED_FEATURES if f != "dst_port"]

    X = df[ORDERED_FEATURES]
    y = df["label"]

    print(f"\n[Stage 6] Performing stratified 80/20 train/test split (random_state=42)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )
    print(f"  - Train samples: {len(X_train):,d} | Test samples: {len(X_test):,d}")

    # -------------------------------------------------------------------------
    # Variant A: With dst_port
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("TRAINING VARIANT A: With `dst_port` (19 features)")
    print("=" * 70)
    rf_with_port = RandomForestClassifier(
        n_estimators=150,
        n_jobs=-1,
        class_weight="balanced",
        random_state=42,
    )
    rf_with_port.fit(X_train[features_with_port], y_train)
    y_pred_A = rf_with_port.predict(X_test[features_with_port])

    report_A = classification_report(
        y_test, y_pred_A, labels=TARGET_CLASSES, target_names=TARGET_CLASSES, zero_division=0, output_dict=True
    )
    macro_f1_A = float(report_A["macro avg"]["f1-score"])
    print(classification_report(y_test, y_pred_A, labels=TARGET_CLASSES, target_names=TARGET_CLASSES, zero_division=0, digits=4))
    print(f"Variant A Macro-F1: {macro_f1_A:.4f}")

    # -------------------------------------------------------------------------
    # Variant B: Without dst_port
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("TRAINING VARIANT B: Without `dst_port` (18 features)")
    print("=" * 70)
    rf_without_port = RandomForestClassifier(
        n_estimators=150,
        n_jobs=-1,
        class_weight="balanced",
        random_state=42,
    )
    rf_without_port.fit(X_train[features_without_port], y_train)
    y_pred_B = rf_without_port.predict(X_test[features_without_port])

    report_B = classification_report(
        y_test, y_pred_B, labels=TARGET_CLASSES, target_names=TARGET_CLASSES, zero_division=0, output_dict=True
    )
    macro_f1_B = float(report_B["macro avg"]["f1-score"])
    print(classification_report(y_test, y_pred_B, labels=TARGET_CLASSES, target_names=TARGET_CLASSES, zero_division=0, digits=4))
    print(f"Variant B Macro-F1: {macro_f1_B:.4f}")

    # -------------------------------------------------------------------------
    # Model Selection & Artifact Generation
    # -------------------------------------------------------------------------
    if macro_f1_A >= macro_f1_B:
        winner_name = "with_dst_port"
        winner_model = rf_with_port
        winner_features = features_with_port
        winner_y_pred = y_pred_A
        winner_report = report_A
    else:
        winner_name = "without_dst_port"
        winner_model = rf_without_port
        winner_features = features_without_port
        winner_y_pred = y_pred_B
        winner_report = report_B

    print("\n" + "=" * 70)
    print(f"SELECTION: Winning Variant is '{winner_name}' (Macro-F1: {winner_report['macro avg']['f1-score']:.4f})")
    print("=" * 70)

    # 1. Save model.pkl
    model_path = os.path.join(artifacts_dir, "model.pkl")
    joblib.dump(winner_model, model_path)
    print(f"[Artifact Saved] Model binary -> {model_path}")

    # 2. Save features.json
    features_json_data = {
        "features": winner_features,
        "features_count": len(winner_features),
        "selected_variant": winner_name,
        "classes": TARGET_CLASSES,
        "alert_threshold": ALERT_THRESHOLD,
    }
    features_path = os.path.join(artifacts_dir, "features.json")
    with open(features_path, "w", encoding="utf-8") as f:
        json.dump(features_json_data, f, indent=2)
    print(f"[Artifact Saved] Feature schema -> {features_path}")

    # 3. Save metrics.json
    cm = confusion_matrix(y_test, winner_y_pred, labels=TARGET_CLASSES).tolist()
    metrics_data = {
        "selected_variant": winner_name,
        "variant_with_dst_port": {
            "macro_f1": macro_f1_A,
            "weighted_f1": report_A["weighted avg"]["f1-score"],
            "accuracy": report_A["accuracy"],
            "per_class": {cls: report_A[cls] for cls in TARGET_CLASSES if cls in report_A},
        },
        "variant_without_dst_port": {
            "macro_f1": macro_f1_B,
            "weighted_f1": report_B["weighted avg"]["f1-score"],
            "accuracy": report_B["accuracy"],
            "per_class": {cls: report_B[cls] for cls in TARGET_CLASSES if cls in report_B},
        },
        "winning_confusion_matrix": {
            "labels": TARGET_CLASSES,
            "matrix": cm,
        },
    }
    metrics_path = os.path.join(artifacts_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=2)
    print(f"[Artifact Saved] Metrics data -> {metrics_path}")

    # 4. Save confusion_matrix.png
    plt.figure(figsize=(8, 6))
    cm_arr = np.array(cm)
    plt.imshow(cm_arr, interpolation="nearest", cmap=plt.cm.Blues)
    plt.title(f"Confusion Matrix ({winner_name})")
    plt.colorbar()
    tick_marks = np.arange(len(TARGET_CLASSES))
    plt.xticks(tick_marks, TARGET_CLASSES, rotation=45)
    plt.yticks(tick_marks, TARGET_CLASSES)

    thresh = cm_arr.max() / 2.0
    for i in range(cm_arr.shape[0]):
        for j in range(cm_arr.shape[1]):
            plt.text(
                j, i, f"{cm_arr[i, j]:,d}",
                horizontalalignment="center",
                color="white" if cm_arr[i, j] > thresh else "black",
            )

    plt.ylabel("True Label")
    plt.xlabel("Predicted Label")
    plt.tight_layout()
    cm_plot_path = os.path.join(artifacts_dir, "confusion_matrix.png")
    plt.savefig(cm_plot_path, dpi=150)
    plt.close()
    print(f"[Artifact Saved] Confusion Matrix Plot -> {cm_plot_path}")

    # 5. Save feature_importance.png
    importances = winner_model.feature_importances_
    indices = np.argsort(importances)[::-1]
    sorted_features = [winner_features[i] for i in indices]
    sorted_importances = importances[indices]

    plt.figure(figsize=(10, 6))
    plt.title(f"Feature Importances ({winner_name})")
    plt.barh(range(len(sorted_features)), sorted_importances[::-1], align="center", color="#2b5c8f")
    plt.yticks(range(len(sorted_features)), sorted_features[::-1])
    plt.xlabel("Gini Importance")
    plt.tight_layout()
    fi_plot_path = os.path.join(artifacts_dir, "feature_importance.png")
    plt.savefig(fi_plot_path, dpi=150)
    plt.close()
    print(f"[Artifact Saved] Feature Importance Plot -> {fi_plot_path}")

    # Save a small held-out test sample CSV for ml/test_model.py verification
    sample_test_path = os.path.join(artifacts_dir, "held_out_sample.csv")
    test_sample = X_test.copy()
    test_sample["true_label"] = y_test
    test_sample.head(20).to_csv(sample_test_path, index=False)
    print(f"[Artifact Saved] Held-out test sample -> {sample_test_path}")

    print("\n[Done] Model training and artifact export completed successfully.")


def main():
    parser = argparse.ArgumentParser(description="NetGuard AI Model Training Pipeline")
    parser.add_argument("--data-dir", type=str, default="data/raw", help="Directory containing raw CICIDS2017 CSVs")
    parser.add_argument("--artifacts-dir", type=str, default="ml/artifacts", help="Output directory for model artifacts")
    parser.add_argument("--sample-max-rows", type=int, default=None, help="Debug option to read max rows per CSV")
    parser.add_argument("--max-per-class", type=int, default=MAX_ROWS_PER_CLASS, help="Maximum rows per attack class")
    args = parser.parse_args()

    df = load_raw_data(args.data_dir, sample_max_rows=args.sample_max_rows)
    df = map_and_convert(df)
    df = clean_data(df)
    df = filter_and_sample_labels(df, max_per_class=args.max_per_class)
    train_and_evaluate(df, artifacts_dir=args.artifacts_dir)


if __name__ == "__main__":
    main()
