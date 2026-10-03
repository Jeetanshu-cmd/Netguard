"""Fallback mode: no live sniffing needed.

    python -m capture.replay --pcap lab.pcap            # packets -> flows -> API
    python -m capture.replay --csv ml/artifacts/held_out_sample.csv

--pcap runs a capture file through the exact same parse -> flow table -> features
path as the live sniffer. --csv takes rows that already hold the 19 NetGuard
features (in NetGuard units, seconds not microseconds) and submits them as flows.

Both modes submit to /ingest/flows with the sensor key, so the dashboard updates
live. Use --dry-run to print the flows instead.
"""
from __future__ import annotations

import argparse
import csv
import logging
import math
import os
import time
from typing import Callable, Optional

from capture.client import (
    FlowClient, flow_to_payload, load_dotenv, make_payload, print_payload,
)
from capture.features import FEATURE_ORDER
from capture.flow_table import FlowTable

log = logging.getLogger("netguard.capture.replay")

INT_FEATURES = {
    "dst_port", "fwd_packets", "bwd_packets", "fwd_bytes", "bwd_bytes",
    "syn_count", "ack_count", "fin_count", "rst_count", "psh_count",
}


def replay_pcap(path: str, sink: Callable[[dict], None],
                idle_timeout: float = 5.0, active_timeout: float = 30.0) -> int:
    """Run a pcap through the live pipeline. Returns the number of flows emitted."""
    from scapy.all import sniff                      # lazy: CSV mode needs no Scapy
    from capture.sniffer import PacketHandler

    count = 0

    def emit(flow) -> None:
        nonlocal count
        count += 1
        sink(flow_to_payload(flow))

    table = FlowTable(emit, idle_timeout=idle_timeout, active_timeout=active_timeout)
    sniff(offline=path, store=False, prn=PacketHandler(table))
    table.flush()
    return count


def _parse_row(row: dict) -> dict:
    features = {}
    for name in FEATURE_ORDER:
        value = float(row[name])
        if not math.isfinite(value):
            raise ValueError(f"{name} is not finite")
        features[name] = int(value) if name in INT_FEATURES else value
    return features


def replay_csv(path: str, sink: Callable[[dict], None],
               delay: float = 0.2, limit: Optional[int] = None) -> int:
    """Submit each CSV row as a flow. Returns the number of flows submitted.
    Extra columns (e.g. label) are ignored; src_ip/dst_ip columns are optional."""
    sent = skipped = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = [c.strip() for c in (reader.fieldnames or [])]
        missing = [c for c in FEATURE_ORDER if c not in columns]
        if missing:
            raise ValueError(f"CSV is missing feature columns: {missing}")
        reader.fieldnames = columns
        for row in reader:
            if limit is not None and sent >= limit:
                break
            try:
                features = _parse_row(row)
            except (ValueError, TypeError, KeyError):
                skipped += 1
                continue
            sink(make_payload(features,
                              row.get("src_ip") or "0.0.0.0",
                              row.get("dst_ip") or "0.0.0.0",
                              time.time()))
            sent += 1
            if delay:
                time.sleep(delay)
    if skipped:
        log.warning("skipped %d malformed rows", skipped)
    return sent


def main(argv=None) -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="NetGuard replay (fallback mode)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--pcap", help="packet capture file")
    src.add_argument("--csv", help="CSV with the 19 NetGuard feature columns")
    p.add_argument("--api-url", default=os.environ.get("NETGUARD_API_URL", "http://localhost:8000"))
    p.add_argument("--api-key", default=os.environ.get("SENSOR_API_KEY", ""))
    p.add_argument("--delay", type=float, default=0.2, help="seconds between CSV rows (demo pacing)")
    p.add_argument("--limit", type=int, default=None, help="max CSV rows")
    p.add_argument("--idle-timeout", type=float, default=5.0)
    p.add_argument("--active-timeout", type=float, default=30.0)
    p.add_argument("--buffer-size", type=int, default=100_000,
                   help="replay is bursty, so use a larger buffer than the live sensor")
    p.add_argument("--dry-run", action="store_true", help="print flows instead of POSTing")
    args = p.parse_args(argv)
    if not args.dry_run and not args.api_key:
        p.error("SENSOR_API_KEY is not set (put it in .env or pass --api-key)")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    client = None
    if args.dry_run:
        sink = print_payload
    else:
        client = FlowClient(args.api_url, args.api_key, buffer_size=args.buffer_size)
        client.start()
        sink = client.submit

    try:
        if args.pcap:
            n = replay_pcap(args.pcap, sink, args.idle_timeout, args.active_timeout)
        else:
            n = replay_csv(args.csv, sink, args.delay, args.limit)
    finally:
        if client:
            client.close(timeout=30.0)
    log.info("replayed %d flows", n)
    if client:
        log.info("sent=%d dropped=%d rejected=%d", client.sent, client.dropped, client.rejected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())