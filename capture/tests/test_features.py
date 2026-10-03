import pytest

from capture.features import (
    ACK, FEATURE_ORDER, FIN, PSH, RST, SYN,
    PacketRecord, extract_features,
)


def handshake_flow():
    # SYN (fwd) -> SYN/ACK (bwd) -> ACK (fwd)
    return [
        PacketRecord(ts=0.0, length=60, is_fwd=True, flags=SYN),
        PacketRecord(ts=0.1, length=60, is_fwd=False, flags=SYN | ACK),
        PacketRecord(ts=0.3, length=52, is_fwd=True, flags=ACK),
    ]


def test_key_order_matches_spec():
    f = extract_features(handshake_flow(), dst_port=80)
    assert list(f.keys()) == FEATURE_ORDER
    assert len(f) == 19


def test_three_packet_handshake_known_values():
    f = extract_features(handshake_flow(), dst_port=80)
    assert f["dst_port"] == 80
    assert f["flow_duration_s"] == pytest.approx(0.3)
    assert f["fwd_packets"] == 2
    assert f["bwd_packets"] == 1
    assert f["fwd_bytes"] == 112
    assert f["bwd_bytes"] == 60
    assert f["bytes_per_sec"] == pytest.approx(172 / 0.3)
    assert f["packets_per_sec"] == pytest.approx(10.0)
    assert f["pkt_len_mean"] == pytest.approx(172 / 3)
    assert f["pkt_len_std"] == pytest.approx(3.7712, abs=1e-3)  # population std
    assert f["pkt_len_max"] == 60
    assert f["pkt_len_min"] == 52
    assert f["syn_count"] == 2
    assert f["ack_count"] == 2
    assert f["fin_count"] == 0
    assert f["rst_count"] == 0
    assert f["psh_count"] == 0
    assert f["iat_mean"] == pytest.approx(0.15)
    assert f["iat_max"] == pytest.approx(0.2)


def test_single_packet_flow_has_no_nan_or_div_by_zero():
    f = extract_features([PacketRecord(5.0, 60, True, SYN)], dst_port=22)
    assert f["flow_duration_s"] == 0.0
    assert f["bytes_per_sec"] == 0.0
    assert f["packets_per_sec"] == 0.0
    assert f["pkt_len_std"] == 0.0
    assert f["iat_mean"] == 0.0
    assert f["iat_max"] == 0.0
    assert f["bwd_packets"] == 0 and f["bwd_bytes"] == 0


def test_identical_timestamps_are_zero_duration():
    pkts = [PacketRecord(1.0, 60, True, SYN), PacketRecord(1.0, 60, True, SYN)]
    f = extract_features(pkts, dst_port=80)
    assert f["flow_duration_s"] == 0.0
    assert f["packets_per_sec"] == 0.0
    assert f["syn_count"] == 2


def test_unidirectional_syn_flood_flow():
    pkts = [PacketRecord(i * 0.001, 54, True, SYN) for i in range(100)]
    f = extract_features(pkts, dst_port=80)
    assert f["fwd_packets"] == 100 and f["bwd_packets"] == 0
    assert f["syn_count"] == 100 and f["ack_count"] == 0
    assert f["pkt_len_std"] == 0.0


def test_close_flags_counted():
    pkts = [
        PacketRecord(0.0, 60, True, PSH | ACK),
        PacketRecord(0.1, 52, False, FIN | ACK),
        PacketRecord(0.2, 40, True, RST),
    ]
    f = extract_features(pkts, dst_port=443)
    assert (f["psh_count"], f["fin_count"], f["rst_count"], f["ack_count"]) == (1, 1, 1, 2)


def test_non_tcp_packets_have_zero_flags():
    pkts = [PacketRecord(0.0, 80, True), PacketRecord(0.5, 120, False)]
    f = extract_features(pkts, dst_port=53)
    assert f["syn_count"] == f["ack_count"] == f["fin_count"] == 0


def test_out_of_order_input_is_sorted_by_timestamp():
    pkts = list(reversed(handshake_flow()))
    f = extract_features(pkts, dst_port=80)
    assert f["flow_duration_s"] == pytest.approx(0.3)
    assert f["iat_max"] == pytest.approx(0.2)


def test_empty_flow_raises():
    with pytest.raises(ValueError):
        extract_features([], dst_port=80)