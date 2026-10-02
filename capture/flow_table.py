"""Flow table: groups packets into bidirectional flows and expires them.

Pure Python, no Scapy import. The sniffer parses each Scapy packet into plain
fields and calls FlowTable.add_packet(). Timeouts use packet timestamps (not
wall-clock), so live sniffing and pcap replay behave identically.

A flow expires when it is:
  * idle for more than `idle_timeout` seconds,
  * older than `active_timeout` seconds (long flows are split), or
  * closed: `close_linger` seconds after the first FIN/RST. The linger lets the
    trailing ACKs of a FIN handshake join the flow instead of creating a bogus
    one-packet flow.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from capture.features import FIN, RST, PacketRecord, extract_features

Endpoint = tuple[str, int]
FlowKey = tuple[Endpoint, Endpoint, int]


def make_key(src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: int) -> FlowKey:
    """Canonical key: A->B and B->A map to the same flow."""
    a, b = (src_ip, src_port), (dst_ip, dst_port)
    return (a, b, proto) if a <= b else (b, a, proto)


@dataclass
class Flow:
    key: FlowKey
    src_ip: str          # initiator = sender of the first packet
    src_port: int
    dst_ip: str
    dst_port: int
    proto: int
    first_ts: float
    last_ts: float
    packets: list[PacketRecord] = field(default_factory=list)
    closing_since: Optional[float] = None

    def features(self) -> dict:
        return extract_features(self.packets, self.dst_port)


class FlowTable:
    def __init__(
        self,
        on_expire: Callable[[Flow], None],
        idle_timeout: float = 5.0,
        active_timeout: float = 30.0,
        close_linger: float = 1.0,
    ):
        self._on_expire = on_expire
        self.idle_timeout = idle_timeout
        self.active_timeout = active_timeout
        self.close_linger = close_linger
        self._flows: dict[FlowKey, Flow] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._flows)

    def _is_stale(self, flow: Flow, now: float) -> bool:
        if now - flow.last_ts > self.idle_timeout:
            return True
        if now - flow.first_ts >= self.active_timeout:
            return True
        if flow.closing_since is not None and now - flow.closing_since >= self.close_linger:
            return True
        return False

    def add_packet(
        self,
        ts: float,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
        proto: int,
        length: int,
        flags: int = 0,
    ) -> None:
        key = make_key(src_ip, src_port, dst_ip, dst_port, proto)
        expired: list[Flow] = []
        with self._lock:
            flow = self._flows.get(key)
            if flow is not None and self._is_stale(flow, ts):
                expired.append(self._flows.pop(key))
                flow = None
            if flow is None:
                flow = Flow(key, src_ip, src_port, dst_ip, dst_port, proto, ts, ts)
                self._flows[key] = flow

            is_fwd = (src_ip, src_port) == (flow.src_ip, flow.src_port)
            flow.packets.append(PacketRecord(ts, length, is_fwd, flags))
            flow.last_ts = max(flow.last_ts, ts)
            if flags & (FIN | RST) and flow.closing_since is None:
                flow.closing_since = ts

        for f in expired:           # callbacks run outside the lock
            self._on_expire(f)

    def sweep(self, now: float) -> None:
        """Expire every stale flow. Call periodically (live) or per packet (replay)."""
        with self._lock:
            keys = [k for k, f in self._flows.items() if self._is_stale(f, now)]
            expired = [self._flows.pop(k) for k in keys]
        for f in expired:
            self._on_expire(f)

    def flush(self) -> None:
        """Expire everything (end of replay / shutdown)."""
        with self._lock:
            expired = list(self._flows.values())
            self._flows.clear()
        for f in expired:
            self._on_expire(f)