# NetGuard AI — Agent Specification & System Contract

## 1. Project Summary & Architecture

**NetGuard AI** is a college mini project for AI-driven network attack forecasting and detection.

### Pipeline
1. **Packet Capture & Flow Aggregation**: `Scapy` captures raw network packets on a live network interface and aggregates them into bidirectional flows using a sliding time window.
2. **Feature Extraction**: Computes 19 statistical flow features directly from raw packet headers and timestamps.
3. **Inference**: Sends flow feature vectors to a lightweight **FastAPI ML service**.
4. **Live Alerting**: Classification results and confidence scores are pushed in real time via **WebSocket** to an interactive dashboard.
5. **Fallback / Offline Mode**: A CSV replay mode processes pre-recorded packet logs or historical flow CSVs without requiring live sniffing.

### Technology Stack
- **Languages & Core**: Python (3.10+), JavaScript/HTML/CSS
- **ML / Data**: `pandas`, `scikit-learn`, `joblib`
- **Model**: Random Forest Classifier trained on a balanced subset of **CICIDS2017** augmented with locally captured traffic
- **API & Streaming**: **FastAPI** + **Uvicorn** (REST + WebSocket)
- **Database**: **SQLite** (local persistence for scan history and alert events)
- **Packet Processing**: **Scapy**
- **Frontend Dashboard**: **React** + **Chart.js**
- **Strict Constraints**: No Node.js, No MongoDB, No Kafka, No Docker.

---

## 2. Target Attack Classes

Predictions use standardized string labels:

| Class Name | Description | Example Network Behavior |
|---|---|---|
| `Benign` | Legitimate background traffic | Normal web browsing (HTTP/HTTPS), DNS lookups, streaming |
| `DoS_DDoS` | Denial of Service / Distributed DoS | High packet rates, repeated SYN bursts, volumetric floods (e.g. Hulk, Slowloris, SYN flood) |
| `PortScan` | Network reconnaissance and probing | Rapid connections across diverse destination ports, SYN without ACK completion |
| `BruteForce` | Automated authentication attacks | Repeated rapid attempts against services like SSH, FTP, or HTTP auth |

---

## 3. Flow Features Specification

All 19 features are computable directly from raw packets in `Scapy`. They **must** be provided in the exact order specified below for model consistency.

### Feature Table & CICIDS2017 Mapping

| # | Feature Name | Definition | Unit in NetGuard | Matching CICIDS2017 Column | Conversion / Formula | Match Status | Notes & Flags |
|---|---|---|---|---|---|---|---|
| 1 | `dst_port` | Destination port of the connection | Integer (0–65535) | ` Destination Port` | None (`dst_port = col`) | **Exact** | Identifies target protocol/service. |
| 2 | `flow_duration_s` | Total elapsed duration of the flow | Seconds (float) | ` Flow Duration` | `flow_duration_s = col / 1,000,000.0` | **Scale Mismatch** | CICIDS2017 records duration in **microseconds (μs)**. Must divide by $10^6$ when loading CICIDS2017 data. Single-packet flows have duration 0. |
| 3 | `fwd_packets` | Count of packets sent in forward direction (initiator -> target) | Integer count | ` Total Fwd Packets` | None (`fwd_packets = col`) | **Exact** | Forward direction is determined by first packet in flow. |
| 4 | `bwd_packets` | Count of packets sent in backward direction (target -> initiator) | Integer count | ` Total Backward Packets` | None (`bwd_packets = col`) | **Exact** | In unidirectional attacks (e.g. UDP/SYN flood), this is often 0. |
| 5 | `fwd_bytes` | Total byte volume in forward direction (headers + payloads) | Integer bytes | `Total Length of Fwd Packets` | None (`fwd_bytes = col`) | **Exact** | Raw IP packet length (`len(pkt)`). |
| 6 | `bwd_bytes` | Total byte volume in backward direction (headers + payloads) | Integer bytes | ` Total Length of Bwd Packets` | None (`bwd_bytes = col`) | **Exact** | 0 for unidirectional flows. |
| 7 | `bytes_per_sec` | Total flow byte throughput rate | Bytes / second (float) | `Flow Bytes/s` | `(fwd_bytes + bwd_bytes) / flow_duration_s` | **Derived / Exact** | Division by zero risk if `flow_duration_s == 0`. Must clamp/handle zero-duration flows (default to 0.0 or total bytes / epsilon). |
| 8 | `packets_per_sec` | Total flow packet transmission rate | Packets / second (float) | ` Flow Packets/s` | `(fwd_packets + bwd_packets) / flow_duration_s` | **Derived / Exact** | Same zero-duration handling required as `bytes_per_sec`. In CICIDS2017, represented as `(Fwd Pkts + Bwd Pkts) / (Flow Duration / 1e6)`. |
| 9 | `pkt_len_mean` | Arithmetic mean of lengths across all packets in flow | Bytes (float) | ` Packet Length Mean` | `sum(pkt_lengths) / total_packets` | **Exact** | CICIDS2017 has both ` Packet Length Mean` and ` Average Packet Size`. `Packet Length Mean` is the precise match. |
| 10 | `pkt_len_std` | Standard deviation of packet lengths across flow | Bytes (float) | ` Packet Length Std` | Population or sample std dev of packet lengths | **Exact** | Zero when all packets are identical or when single packet observed. |
| 11 | `pkt_len_max` | Maximum packet length observed in flow | Bytes (float/int) | ` Max Packet Length` | `max(pkt_lengths)` | **Exact** | In CICIDS2017 raw files, column is named ` Max Packet Length`. |
| 12 | `pkt_len_min` | Minimum packet length observed in flow | Bytes (float/int) | ` Min Packet Length` | `min(pkt_lengths)` | **Exact** | In CICIDS2017 raw files, column is named ` Min Packet Length`. |
| 13 | `syn_count` | Total packets in flow with TCP SYN flag set | Integer count | ` SYN Flag Count` | Scapy: `sum(1 for p in pkts if TCP in p and p[TCP].flags.S)` | **Flagged (Bug in CICIDS2017)** | In CICIDS2017, original CICFlowMeter has documented anomalies (e.g. inverted flags or partial zeroing in certain CSV subsets). NetGuard counts true SYN occurrences. |
| 14 | `ack_count` | Total packets in flow with TCP ACK flag set | Integer count | ` ACK Flag Count` | Scapy: `sum(1 for p in pkts if TCP in p and p[TCP].flags.A)` | **Flagged (Bug in CICIDS2017)** | Similar to SYN, CICIDS2017 ACK flag counts exhibited parser irregularities in CICFlowMeter. |
| 15 | `fin_count` | Total packets in flow with TCP FIN flag set | Integer count | `FIN Flag Count` | Scapy: `sum(1 for p in pkts if TCP in p and p[TCP].flags.F)` | **Exact / Flagged** | CICFlowMeter header in some CSVs is `FIN Flag Count` (no leading space). |
| 16 | `rst_count` | Total packets in flow with TCP RST flag set | Integer count | ` RST Flag Count` | Scapy: `sum(1 for p in pkts if TCP in p and p[TCP].flags.R)` | **Exact** | Useful for reset scans and aborted handshakes. |
| 17 | `psh_count` | Total packets in flow with TCP PSH flag set | Integer count | ` PSH Flag Count` | Scapy: `sum(1 for p in pkts if TCP in p and p[TCP].flags.P)` | **Flagged (Bug in CICIDS2017)** | CICFlowMeter had known swapped logic between SYN and PSH flag counts on certain traffic days. |
| 18 | `iat_mean` | Mean inter-arrival time between successive packets in flow | Seconds (float) | `Flow IAT Mean` | `iat_mean = col / 1,000,000.0` | **Scale Mismatch** | CICIDS2017 `Flow IAT Mean` is in **microseconds (μs)**. In Scapy, packet timestamps yield seconds. 0 for single-packet flows. |
| 19 | `iat_max` | Maximum inter-arrival time between successive packets in flow | Seconds (float) | ` Flow IAT Max` | `iat_max = col / 1,000,000.0` | **Scale Mismatch** | In microseconds in CICIDS2017. 0 for single-packet flows. |

---

## 4. API Contract

The FastAPI backend exposes both RESTful endpoints and real-time WebSocket communication.

### REST Endpoints

#### `POST /predict`
Performs classification on a single flow feature dictionary.

- **Request Body**:
  ```json
  {
    "features": {
      "dst_port": 80,
      "flow_duration_s": 0.0452,
      "fwd_packets": 5,
      "bwd_packets": 4,
      "fwd_bytes": 350,
      "bwd_bytes": 1200,
      "bytes_per_sec": 34292.03,
      "packets_per_sec": 199.11,
      "pkt_len_mean": 172.22,
      "pkt_len_std": 145.3,
      "pkt_len_max": 540,
      "pkt_len_min": 54,
      "syn_count": 1,
      "ack_count": 8,
      "fin_count": 1,
      "rst_count": 0,
      "psh_count": 2,
      "iat_mean": 0.0056,
      "iat_max": 0.0120
    }
  }
  ```
- **Response Body**:
  ```json
  {
    "label": "Benign",
    "confidence": 0.9642,
    "top_features": [
      {"feature": "flow_duration_s", "value": 0.0452, "importance": 0.182},
      {"feature": "pkt_len_mean", "value": 172.22, "importance": 0.141},
      {"feature": "dst_port", "value": 80, "importance": 0.125}
    ]
  }
  ```

#### `POST /predict/batch`
Classifies a collection of flows (e.g. from a CSV upload or chunked capture).

- **Request Body**:
  ```json
  {
    "flows": [
      {
        "id": "flow-1001",
        "src_ip": "192.168.1.15",
        "dst_ip": "192.168.1.1",
        "features": { ... }
      }
    ]
  }
  ```
- **Response Body**:
  ```json
  {
    "results": [
      {
        "id": "flow-1001",
        "label": "PortScan",
        "confidence": 0.9410,
        "top_features": [...]
      }
    ]
  }
  ```

#### `GET /health`
Checks API and model health status.

- **Response Body**:
  ```json
  {
    "status": "healthy",
    "model_loaded": true,
    "timestamp": "2026-09-20T16:15:00Z"
  }
  ```

#### `GET /model-info`
Returns metadata describing the active model and feature schema.

- **Response Body**:
  ```json
  {
    "model_type": "RandomForestClassifier",
    "classes": ["Benign", "DoS_DDoS", "PortScan", "BruteForce"],
    "features_count": 19,
    "features": [
      "dst_port", "flow_duration_s", "fwd_packets", "bwd_packets",
      "fwd_bytes", "bwd_bytes", "bytes_per_sec", "packets_per_sec",
      "pkt_len_mean", "pkt_len_std", "pkt_len_max", "pkt_len_min",
      "syn_count", "ack_count", "fin_count", "rst_count", "psh_count",
      "iat_mean", "iat_max"
    ],
    "alert_threshold": 0.85
  }
  ```

---

### WebSocket Endpoint: `/ws/flows`

A persistent WebSocket connection broadcasting classified flows to frontend clients.

- **Connection URL**: `ws://localhost:8000/ws/flows`
- **Event Schema**:
  ```json
  {
    "id": "flow-20260920-00042",
    "timestamp": 1790000000.123,
    "src_ip": "192.168.1.45",
    "dst_ip": "192.168.1.1",
    "dst_port": 22,
    "label": "BruteForce",
    "confidence": 0.9125,
    "top_features": [
      {"feature": "fwd_packets", "value": 140, "importance": 0.22},
      {"feature": "dst_port", "value": 22, "importance": 0.19}
    ]
  }
  ```

---

## 5. Architectural Rules & Invariants

1. **Artifact Coupling**:
   - `model.pkl` must always be saved and loaded alongside `features.json`.
   - `features.json` explicitly lists the ordered feature names and preprocessing parameters (scalers/imputers) to ensure 100% feature-order fidelity between training and inference.
2. **Label Representation**:
   - Internal model integer classes are strictly converted to string labels (`"Benign"`, `"DoS_DDoS"`, `"PortScan"`, `"BruteForce"`) before exiting the ML service boundary.
3. **Alerting Threshold**:
   - High-confidence alerts fire **only** when `label != "Benign"` and `confidence > 0.85`.
4. **Modularity**:
   - One module per task. Stop and summarize before proceeding.
   - Sniffing or intrusive network scanners (e.g. `nmap`) are **never** executed by autonomous agents; they are strictly run manually by the user.
   - Code must remain clean, minimal, and dependency-light.
