"""Sends flows to the API (POST /ingest/flows, X-API-Key header).

Standard library only. The sensor must never crash or stall because the backend
is down, so flows go into a bounded in-memory buffer and a background thread
delivers them in batches, retrying with backoff:

  * network error / 5xx / 429  -> keep the batch, retry later (exponential backoff)
  * other 4xx (bad key, bad schema) -> log an error and drop that batch, because
    retrying a request the server will always refuse would block everything behind it
  * buffer full -> drop the OLDEST flow, so memory stays bounded
"""
from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request
import uuid
from collections import deque
from typing import Callable, Optional

log = logging.getLogger("netguard.capture.client")

INGEST_PATH = "/ingest/flows"


# ---------------------------------------------------------------- helpers
def load_dotenv(path: str = ".env") -> None:
    """Tiny KEY=VALUE loader so `cp .env.example .env` works in development.
    Never overrides variables that are already set (systemd/shell win)."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def new_flow_id() -> str:
    return f"flow-{uuid.uuid4().hex[:12]}"


def make_payload(features: dict, src_ip: str, dst_ip: str, ts: float,
                 src_port: int = 0, protocol: int = 0) -> dict:
    """One flow as sent to the API. Same shape as /predict/batch items in
    AGENTS.md (id, src_ip, dst_ip, features) plus a few extra context fields."""
    return {
        "id": new_flow_id(),            # lets the API de-duplicate retried batches
        "timestamp": ts,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": src_port,
        "dst_port": features["dst_port"],
        "protocol": protocol,
        "features": features,
    }


def flow_to_payload(flow) -> dict:
    return make_payload(flow.features(), flow.src_ip, flow.dst_ip,
                        flow.last_ts, flow.src_port, flow.proto)


def print_payload(payload: dict) -> None:
    """--dry-run sink: print instead of POSTing."""
    print(json.dumps(payload))


# ---------------------------------------------------------------- client
class Rejected(Exception):
    """The API refused the request in a way retrying will not fix."""


class FlowClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        buffer_size: int = 1000,
        batch_size: int = 50,
        flush_interval: float = 1.0,
        timeout: float = 5.0,
        max_backoff: float = 30.0,
        post: Optional[Callable[[dict], None]] = None,   # injectable for tests
    ):
        self.url = api_url.rstrip("/") + INGEST_PATH
        self.api_key = api_key
        self.buffer_size = buffer_size
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.timeout = timeout
        self.max_backoff = max_backoff
        self._post = post or self._http_post

        self._buf: deque = deque()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._backoff = 0.0

        self.sent = 0
        self.dropped = 0     # lost to a full buffer
        self.rejected = 0    # refused by the API (non-retryable)

    # -- producer side (called from the sniffer thread; must be fast)
    def submit(self, payload: dict) -> None:
        with self._lock:
            if len(self._buf) >= self.buffer_size:
                self._buf.popleft()
                self.dropped += 1
                if self.dropped % 100 == 1:
                    log.warning("buffer full, dropping oldest flows (dropped=%d)", self.dropped)
            self._buf.append(payload)
            batch_ready = len(self._buf) >= self.batch_size
        if batch_ready:
            self._wake.set()

    def pending(self) -> int:
        with self._lock:
            return len(self._buf)

    # -- consumer side
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="flow-client", daemon=True)
        self._thread.start()

    def flush_once(self) -> bool:
        """Send one batch. False = delivery failed and the batch was re-queued."""
        with self._lock:
            n = min(self.batch_size, len(self._buf))
            batch = [self._buf.popleft() for _ in range(n)]
        if not batch:
            return True
        try:
            self._post({"flows": batch})
        except Rejected as e:
            log.error("API rejected %d flows (%s); dropping them", len(batch), e)
            self.rejected += len(batch)
            self._backoff = 0.0
            return True
        except Exception as e:  # network error, timeout, 5xx, 429
            log.warning("API unreachable (%s); %d flows kept for retry", e, len(batch))
            with self._lock:
                self._buf.extendleft(reversed(batch))
                while len(self._buf) > self.buffer_size:
                    self._buf.popleft()
                    self.dropped += 1
            self._backoff = min(max(1.0, self._backoff * 2), self.max_backoff)
            return False
        self.sent += len(batch)
        self._backoff = 0.0
        return True

    def _drain(self) -> None:
        while self.pending() and self.flush_once():
            pass

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(self.flush_interval + self._backoff)
            self._wake.clear()
            self._drain()

    def close(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)
        self._drain()                       # one last best-effort delivery
        left = self.pending()
        if left:
            log.warning("shutting down with %d unsent flows", left)

    def _http_post(self, body: dict) -> None:
        req = urllib.request.Request(
            self.url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-API-Key": self.api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code not in (408, 429):
                raise Rejected(f"HTTP {e.code}") from e
            raise