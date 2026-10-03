from capture.features import ACK, FEATURE_ORDER, FIN, SYN
from capture.flow_table import FlowTable, make_key

A, B = ("10.0.0.1", 40000), ("10.0.0.2", 80)
TCP = 6


def table(**kw):
    out = []
    return FlowTable(out.append, **kw), out


def pkt(t, ts, src, dst, length=60, flags=0, proto=TCP):
    t.add_packet(ts, src[0], src[1], dst[0], dst[1], proto, length, flags)


def test_key_is_direction_independent():
    assert make_key(*A, *B, TCP) == make_key(*B, *A, TCP)


def test_both_directions_form_one_flow():
    t, out = table()
    pkt(t, 0.0, A, B, flags=SYN)
    pkt(t, 0.1, B, A, flags=SYN | ACK)
    assert len(t) == 1
    t.flush()
    f = out[0]
    assert (f.src_ip, f.dst_ip, f.dst_port) == ("10.0.0.1", "10.0.0.2", 80)
    feats = f.features()
    assert feats["fwd_packets"] == 1 and feats["bwd_packets"] == 1


def test_first_packet_defines_forward_even_if_it_is_the_server():
    t, out = table()
    pkt(t, 0.0, B, A)           # server speaks first
    t.flush()
    assert out[0].dst_port == 40000


def test_different_ports_are_different_flows():
    t, out = table()
    for port in (22, 80, 443):
        pkt(t, 0.0, A, ("10.0.0.2", port), flags=SYN)
    assert len(t) == 3


def test_idle_timeout_via_sweep():
    t, out = table(idle_timeout=5.0)
    pkt(t, 0.0, A, B)
    t.sweep(4.9)
    assert out == []
    t.sweep(5.1)
    assert len(out) == 1 and len(t) == 0


def test_packet_after_idle_gap_starts_new_flow():
    t, out = table(idle_timeout=5.0)
    pkt(t, 0.0, A, B)
    pkt(t, 10.0, A, B)
    assert len(out) == 1 and len(out[0].packets) == 1
    assert len(t) == 1


def test_active_timeout_splits_long_flow():
    t, out = table(idle_timeout=5.0, active_timeout=30.0)
    for ts in range(0, 32, 2):  # packet every 2s, never idle
        pkt(t, float(ts), A, B)
    assert len(out) == 1
    assert out[0].last_ts - out[0].first_ts < 30.0


def test_fin_lingers_then_expires_and_trailing_ack_joins_flow():
    t, out = table(close_linger=1.0)
    pkt(t, 0.0, A, B, flags=SYN)
    pkt(t, 0.2, A, B, flags=FIN | ACK)
    pkt(t, 0.4, B, A, flags=ACK)          # inside linger: same flow
    assert out == []
    t.sweep(1.3)                          # linger over
    assert len(out) == 1 and len(out[0].packets) == 3


def test_flush_emits_everything():
    t, out = table()
    pkt(t, 0.0, A, B)
    pkt(t, 0.0, A, ("10.0.0.3", 22))
    t.flush()
    assert len(out) == 2 and len(t) == 0


def test_expired_flow_yields_19_ordered_features():
    t, out = table()
    pkt(t, 0.0, A, B, flags=SYN)
    pkt(t, 0.5, B, A, flags=SYN | ACK)
    t.flush()
    assert list(out[0].features().keys()) == FEATURE_ORDER