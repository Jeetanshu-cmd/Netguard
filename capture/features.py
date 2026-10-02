"""Flow feature extraction: the 19 features from AGENTS.md section 3.

Pure Python, no Scapy import. flow_table.py converts each Scapy packet into a
PacketRecord; this module only does the math, so it can be unit-tested with
hand-built packets and without root.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

# TCP flag bitmasks (same values as the TCP header).
FIN, SYN, RST, PSH, ACK = 0x01, 0x02, 0x04, 0x08, 0x10

# Exact order required by AGENTS.md section 3 / features.json.
FEATURE_ORDER = [
    "dst_port", "flow_duration_s", "fwd_packets", "bwd_packets",
    "fwd_bytes", "bwd_bytes", "bytes_per_sec", "packets_per_sec",
    "pkt_len_mean", "pkt_len_std", "pkt_len_max", "pkt_len_min",
    "syn_count", "ack_count", "fin_count", "rst_count", "psh_count",
    "iat_mean", "iat_max",
]


@dataclass(frozen=True, slots=True)
class PacketRecord:
    ts: float        # capture timestamp, seconds
    length: int      # bytes (IP-level length, see note in flow_table.py)
    is_fwd: bool     # True if sent by the flow initiator (first packet's sender)
    flags: int = 0   # TCP flag bitmask; 0 for non-TCP packets


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: Sequence[float]) -> float:
    """Population standard deviation; 0.0 for fewer than 2 values."""
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def _rate(total: float, duration: float) -> float:
    """total / duration, or 0.0 for zero-duration flows (spec: no divide-by-zero)."""
    return total / duration if duration > 0 else 0.0


def _count_flag(pkts: Sequence[PacketRecord], flag: int) -> int:
    return sum(1 for p in pkts if p.flags & flag)


def extract_features(packets: Sequence[PacketRecord], dst_port: int) -> dict:
    """Return the 19 features, keys in FEATURE_ORDER, for one finished flow."""
    if not packets:
        raise ValueError("cannot extract features from an empty flow")

    pkts = sorted(packets, key=lambda p: p.ts)
    lengths = [p.length for p in pkts]
    fwd = [p for p in pkts if p.is_fwd]
    bwd = [p for p in pkts if not p.is_fwd]

    duration = pkts[-1].ts - pkts[0].ts
    gaps = [b.ts - a.ts for a, b in zip(pkts, pkts[1:])]

    fwd_bytes = sum(p.length for p in fwd)
    bwd_bytes = sum(p.length for p in bwd)

    return {
        "dst_port": int(dst_port),
        "flow_duration_s": duration,
        "fwd_packets": len(fwd),
        "bwd_packets": len(bwd),
        "fwd_bytes": fwd_bytes,
        "bwd_bytes": bwd_bytes,
        "bytes_per_sec": _rate(fwd_bytes + bwd_bytes, duration),
        "packets_per_sec": _rate(len(pkts), duration),
        "pkt_len_mean": _mean(lengths),
        "pkt_len_std": _std(lengths),
        "pkt_len_max": max(lengths),
        "pkt_len_min": min(lengths),
        "syn_count": _count_flag(pkts, SYN),
        "ack_count": _count_flag(pkts, ACK),
        "fin_count": _count_flag(pkts, FIN),
        "rst_count": _count_flag(pkts, RST),
        "psh_count": _count_flag(pkts, PSH),
        "iat_mean": _mean(gaps),
        "iat_max": max(gaps) if gaps else 0.0,
    }