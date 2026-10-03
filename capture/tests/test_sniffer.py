import pytest

pytest.importorskip("scapy")

from scapy.all import ARP, ICMP, IP, TCP, UDP, Ether  # noqa: E402

from capture.features import ACK, SYN  # noqa: E402
from capture.flow_table import FlowTable  # noqa: E402
from capture.sniffer import PacketHandler, build_bpf, parse_packet  # noqa: E402


def make(layers, ts, pad=b""):
    """Build, serialize, and re-dissect so header fields (ip.len) are filled in,
    like a packet that came off the wire."""
    pkt = Ether(bytes(layers) + pad)
    pkt.time = ts
    return pkt


def tcp(src, sport, dst, dport, flags, ts):
    return make(Ether() / IP(src=src, dst=dst) / TCP(sport=sport, dport=dport, flags=flags), ts)


def test_parse_tcp_syn():
    f = parse_packet(tcp("10.0.0.1", 40000, "10.0.0.2", 80, "S", 123.5))
    assert f == {
        "ts": 123.5, "src_ip": "10.0.0.1", "src_port": 40000,
        "dst_ip": "10.0.0.2", "dst_port": 80, "proto": 6,
        "length": 40, "flags": SYN,
    }


def test_parse_tcp_syn_ack_flags():
    f = parse_packet(tcp("10.0.0.2", 80, "10.0.0.1", 40000, "SA", 1.0))
    assert f["flags"] == SYN | ACK


def test_parse_udp_has_ports_and_no_flags():
    pkt = make(Ether() / IP(src="10.0.0.1", dst="8.8.8.8") / UDP(sport=5353, dport=53) / b"hello", 1.0)
    f = parse_packet(pkt)
    assert (f["proto"], f["src_port"], f["dst_port"], f["flags"]) == (17, 5353, 53, 0)
    assert f["length"] == 20 + 8 + 5


def test_parse_icmp_uses_port_zero():
    pkt = make(Ether() / IP(src="10.0.0.1", dst="10.0.0.2") / ICMP(), 1.0)
    f = parse_packet(pkt)
    assert (f["proto"], f["src_port"], f["dst_port"]) == (1, 0, 0)


def test_non_ip_packet_is_ignored():
    assert parse_packet(make(Ether() / ARP(), 1.0)) is None


def test_length_excludes_ethernet_padding():
    raw = Ether() / IP(src="10.0.0.1", dst="10.0.0.2") / TCP(sport=1, dport=2, flags="S")
    pkt = make(raw, 1.0, pad=b"\x00" * 6)        # short frames get padded on the wire
    assert parse_packet(pkt)["length"] == 40     # IP header + TCP header only


def test_handler_builds_flow_and_expires_it_by_packet_time():
    out = []
    handler = PacketHandler(FlowTable(out.append, idle_timeout=5.0))
    handler(tcp("10.0.0.1", 40000, "10.0.0.2", 80, "S", 100.0))
    handler(tcp("10.0.0.2", 80, "10.0.0.1", 40000, "SA", 100.1))
    handler(tcp("10.0.0.1", 40000, "10.0.0.2", 80, "A", 100.3))
    assert out == []
    # an unrelated packet 10 s later advances packet time and triggers the sweep
    handler(make(Ether() / IP(src="10.0.0.9", dst="8.8.8.8") / UDP(sport=1, dport=53), 110.0))
    assert len(out) == 1
    feats = out[0].features()
    assert feats["fwd_packets"] == 2 and feats["bwd_packets"] == 1
    assert feats["syn_count"] == 2 and feats["ack_count"] == 2
    assert feats["flow_duration_s"] == pytest.approx(0.3)


def test_handler_skips_non_ip_without_error():
    out = []
    PacketHandler(FlowTable(out.append))(make(Ether() / ARP(), 1.0))
    assert out == []


def test_bpf_filter():
    assert build_bpf("http://localhost:8000") == "ip"
    assert build_bpf("http://127.0.0.1:8000") == "ip"
    assert build_bpf("http://10.0.0.5:8000") == "ip and not (host 10.0.0.5 and port 8000)"
    assert build_bpf("https://api.example.com") == "ip and not (host api.example.com and port 443)"