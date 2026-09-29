"""
Tests for api/ws.py — connection lifecycle and broadcast fan-out.

Starlette's TestClient runs the websocket in a background thread with its
own event loop, so we can call the async broadcast_flow()/broadcast_alert()
methods from the main test thread via asyncio.run() while a connection is
open, the same way you'd trigger a broadcast from a synchronous route
handler in production (FastAPI runs sync routes in a thread pool).
"""

import asyncio

from api.ws import manager


def test_client_can_connect_and_disconnect(client):
    with client.websocket_connect("/ws/flows") as ws:
        pass  # connecting and cleanly exiting the `with` block is the test
    assert len(manager.active_connections) == 0


def test_broadcast_flow_reaches_connected_client(client):
    with client.websocket_connect("/ws/flows") as ws:
        flow_payload = {
            "id": "flow-1",
            "src_ip": "10.0.0.5",
            "dst_ip": "10.0.0.2",
            "label": "PortScan",
            "confidence": 0.93,
            "timestamp": 1000.0,
        }
        asyncio.run(manager.broadcast_flow(flow_payload))

        received = ws.receive_json()
        assert received["type"] == "flow"
        assert received["id"] == "flow-1"
        assert received["label"] == "PortScan"


def test_broadcast_alert_reaches_connected_client(client):
    with client.websocket_connect("/ws/flows") as ws:
        alert_payload = {
            "id": 1,
            "src_ip": "10.0.0.5",
            "label": "PortScan",
            "confidence": 0.93,
            "flow_count": 3,
            "status": "open",
            "timestamp": 1000.0,
        }
        asyncio.run(manager.broadcast_alert(alert_payload))

        received = ws.receive_json()
        assert received["type"] == "alert"
        assert received["flow_count"] == 3


def test_broadcast_reaches_multiple_clients(client):
    with client.websocket_connect("/ws/flows") as ws1:
        with client.websocket_connect("/ws/flows") as ws2:
            assert len(manager.active_connections) == 2
            asyncio.run(manager.broadcast_flow({"id": "flow-2", "label": "Benign"}))
            assert ws1.receive_json()["id"] == "flow-2"
            assert ws2.receive_json()["id"] == "flow-2"


def test_disconnected_client_is_dropped_without_crashing_broadcast(client):
    with client.websocket_connect("/ws/flows") as ws1:
        with client.websocket_connect("/ws/flows"):
            pass  # this one disconnects immediately
        # ws1 is still open; broadcasting must not raise even though the
        # second client is already gone.
        asyncio.run(manager.broadcast_flow({"id": "flow-3", "label": "Benign"}))
        received = ws1.receive_json()
        assert received["id"] == "flow-3"