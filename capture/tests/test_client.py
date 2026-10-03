import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from capture.client import FlowClient, Rejected, flow_to_payload, load_dotenv, make_payload
from capture.features import ACK, FEATURE_ORDER, SYN
from capture.flow_table import FlowTable


def payload(i=0):
    feats = {name: 0 for name in FEATURE_ORDER}
    feats["dst_port"] = 80
    return make_payload(feats, "10.0.0.1", "10.0.0.2", ts=float(i))


def client(post, **kw):
    return FlowClient("http://api:8000", "key", post=post, **kw)


def test_payload_from_flow():
    out = []
    t = FlowTable(out.append)
    t.add_packet(0.0, "10.0.0.1", 40000, "10.0.0.2", 80, 6, 60, SYN)
    t.add_packet(0.1, "10.0.0.2", 80, "10.0.0.1", 40000, 6, 60, SYN | ACK)
    t.flush()
    p = flow_to_payload(out[0])
    assert p["src_ip"] == "10.0.0.1" and p["dst_ip"] == "10.0.0.2"
    assert p["src_port"] == 40000 and p["dst_port"] == 80 and p["protocol"] == 6
    assert list(p["features"].keys()) == FEATURE_ORDER
    assert p["id"].startswith("flow-")


def test_success_sends_batch_and_empties_buffer():
    got = []
    c = client(got.append, batch_size=2)
    for i in range(3):
        c.submit(payload(i))
    assert c.flush_once() is True
    assert len(got[0]["flows"]) == 2 and c.pending() == 1 and c.sent == 2


def test_failure_keeps_flows_in_order_and_retries():
    calls = {"n": 0}
    got = []

    def post(body):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("backend down")
        got.append(body)

    c = client(post, batch_size=10)
    for i in range(3):
        c.submit(payload(i))
    assert c.flush_once() is False
    assert c.pending() == 3 and c.sent == 0
    assert c.flush_once() is True
    assert [f["timestamp"] for f in got[0]["flows"]] == [0.0, 1.0, 2.0]


def test_buffer_is_bounded_and_drops_oldest():
    c = client(lambda b: None, buffer_size=3)
    for i in range(5):
        c.submit(payload(i))
    assert c.pending() == 3 and c.dropped == 2
    got = []
    c._post = got.append
    c.flush_once()
    assert [f["timestamp"] for f in got[0]["flows"]] == [2.0, 3.0, 4.0]


def test_failed_retry_cannot_exceed_buffer_size():
    def post(body):
        raise ConnectionError

    c = client(post, buffer_size=3, batch_size=3)
    for i in range(3):
        c.submit(payload(i))
    c.submit(payload(3))                  # evicts 0
    c.flush_once()                        # fails, requeues
    assert c.pending() <= 3


def test_rejected_batch_is_dropped_not_retried():
    def post(body):
        raise Rejected("HTTP 401")

    c = client(post)
    c.submit(payload())
    assert c.flush_once() is True
    assert c.pending() == 0 and c.rejected == 1 and c.sent == 0


def test_background_thread_delivers_and_close_drains():
    got = []
    c = client(got.append, flush_interval=0.05, batch_size=5)
    c.start()
    for i in range(7):
        c.submit(payload(i))
    deadline = time.time() + 3
    while c.sent < 7 and time.time() < deadline:
        time.sleep(0.02)
    c.close()
    assert c.sent == 7


def make_server(status):
    seen = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            seen.append((self.path, self.headers.get("X-API-Key"), json.loads(body)))
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


def test_real_http_post_has_path_key_and_body():
    srv, seen = make_server(200)
    try:
        c = FlowClient(f"http://127.0.0.1:{srv.server_port}", "secret-key")
        c.submit(payload())
        assert c.flush_once() is True
        path, key, body = seen[0]
        assert path == "/ingest/flows" and key == "secret-key"
        assert len(body["flows"]) == 1
    finally:
        srv.shutdown()


@pytest.mark.parametrize("status,expect_pending,expect_rejected", [
    (401, 0, 1),     # bad key: dropped, loudly
    (503, 1, 0),     # server trouble: kept for retry
])
def test_http_error_handling(status, expect_pending, expect_rejected):
    srv, _ = make_server(status)
    try:
        c = FlowClient(f"http://127.0.0.1:{srv.server_port}", "k")
        c.submit(payload())
        c.flush_once()
        assert c.pending() == expect_pending and c.rejected == expect_rejected
    finally:
        srv.shutdown()


def test_unreachable_backend_does_not_raise(unused_port=None):
    c = FlowClient("http://127.0.0.1:9", "k", timeout=0.5)   # nothing listens on :9
    c.submit(payload())
    assert c.flush_once() is False and c.pending() == 1


def test_load_dotenv_does_not_override(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text('# comment\nSENSOR_API_KEY="abc"\nOTHER=1\n')
    monkeypatch.delenv("SENSOR_API_KEY", raising=False)
    monkeypatch.setenv("OTHER", "keep")
    load_dotenv(str(f))
    import os
    assert os.environ["SENSOR_API_KEY"] == "abc" and os.environ["OTHER"] == "keep"