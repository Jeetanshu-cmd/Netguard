"""Live sensor: sniff packets, build flows, send them to the API.

    Linux:   sudo venv/bin/python -m capture.sniffer --iface eth0
    Windows: (Administrator terminal)  python -m capture.sniffer --iface "Wi-Fi"

Only run this on a network you own. `--dry-run` prints the flows instead of
POSTing them, which is handy for checking features against Wireshark.
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from typing import Optional
from urllib.parse import urlparse

from scapy.all import IP, TCP, UDP, AsyncSniffer

from capture.client import FlowClient, flow_to_payload, load_dotenv, print_payload
from capture.flow_table import FlowTable

log = logging.getLogger("netguard.capture.sniffer")

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def parse_packet(pkt) -> Optional[dict]:
    """Scapy packet -> plain fields for FlowTable.add_packet(), or None if not IPv4."""
    if IP not in pkt:
        return None
    ip = pkt[IP]
    src_port = dst_port = flags = 0
    if TCP in pkt:
        l4 = pkt[TCP]
        src_port, dst_port, flags = int(l4.sport), int(l4.dport), int(l4.flags)
    elif UDP in pkt:
        l4 = pkt[UDP]
        src_port, dst_port = int(l4.sport), int(l4.dport)
    # IP-level length from the header field: excludes Ethernet header and any
    # link-layer padding, so values match across interface types.
    length = int(ip.len) if ip.len is not None else len(ip)
    return {
        "ts": float(pkt.time),
        "src_ip": ip.src,
        "src_port": src_port,
        "dst_ip": ip.dst,
        "dst_port": dst_port,
        "proto": int(ip.proto),
        "length": length,
        "flags": flags,
    }


class PacketHandler:
    """Callable for Scapy's prn=. Keeps the callback light: parse, add, and
    sweep expired flows at most once per `sweep_every` seconds of packet time."""

    def __init__(self, table: FlowTable, sweep_every: float = 1.0):
        self.table = table
        self.sweep_every = sweep_every
        self._last_sweep: Optional[float] = None

    def __call__(self, pkt) -> None:
        fields = parse_packet(pkt)
        if fields is None:
            return
        self.table.add_packet(**fields)
        ts = fields["ts"]
        if self._last_sweep is None or ts - self._last_sweep >= self.sweep_every:
            self._last_sweep = ts
            self.table.sweep(ts)


def build_bpf(api_url: str) -> str:
    """Kernel-level filter. Excludes our own API traffic (when the API is on
    another host) so the sensor doesn't report its own POSTs as flows."""
    u = urlparse(api_url)
    host = u.hostname
    if not host or host in LOOPBACK_HOSTS:
        return "ip"
    port = u.port or (443 if u.scheme == "https" else 80)
    return f"ip and not (host {host} and port {port})"


def main(argv=None) -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="NetGuard live capture sensor")
    p.add_argument("--iface", required=True, help='interface name, e.g. eth0 or "Wi-Fi"')
    p.add_argument("--api-url", default=os.environ.get("NETGUARD_API_URL", "http://localhost:8000"))
    p.add_argument("--api-key", default=os.environ.get("SENSOR_API_KEY", ""))
    p.add_argument("--idle-timeout", type=float, default=5.0)
    p.add_argument("--active-timeout", type=float, default=30.0)
    p.add_argument("--dry-run", action="store_true", help="print flows instead of POSTing")
    args = p.parse_args(argv)
    if not args.dry_run and not args.api_key:
        p.error("SENSOR_API_KEY is not set (put it in .env or pass --api-key)")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    client = None
    if args.dry_run:
        sink = print_payload
    else:
        client = FlowClient(args.api_url, args.api_key)
        client.start()
        sink = client.submit

    table = FlowTable(lambda flow: sink(flow_to_payload(flow)),
                      idle_timeout=args.idle_timeout, active_timeout=args.active_timeout)
    bpf = build_bpf(args.api_url)
    sniffer = AsyncSniffer(iface=args.iface, store=False, filter=bpf, prn=PacketHandler(table))

    log.info("sniffing on %s (filter: %s)", args.iface, bpf)
    exit_code = 0
    try:
        sniffer.start()
        while True:
            time.sleep(1.0)
            table.sweep(time.time())        # expire flows even when traffic stops
            thread = getattr(sniffer, "thread", None)
            if thread is not None and not thread.is_alive():
                log.error("sniffer stopped (needs root/admin, or bad interface name?)")
                exit_code = 1
                break
    except KeyboardInterrupt:
        pass
    finally:
        try:
            sniffer.stop()
        except Exception:
            pass
        table.flush()
        if client:
            client.close()
            log.info("sent=%d dropped=%d rejected=%d", client.sent, client.dropped, client.rejected)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())