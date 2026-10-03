import pytest

from capture.features import FEATURE_ORDER
from capture.replay import replay_csv, replay_pcap


def csv_text(rows, extra_cols=()):
    header = list(FEATURE_ORDER) + list(extra_cols)
    lines = [",".join(header)]
    lines += [",".join(str(v) for v in r) for r in rows]
    return "\n".join(lines) + "\n"


GOOD = [80, 0.5, 5, 4, 350, 1200, 3100.0, 18.0, 172.2, 145.3, 540, 54, 1, 8, 1, 0, 2, 0.0056, 0.012]


def test_csv_replay_submits_rows(tmp_path):
    p = tmp_path / "flows.csv"
    p.write_text(csv_text([GOOD + ["Benign"], GOOD + ["Benign"]], extra_cols=["label"]))
    out = []
    n = replay_csv(str(p), out.append, delay=0)
    assert n == 2
    feats = out[0]["features"]
    assert list(feats.keys()) == FEATURE_ORDER
    assert feats["dst_port"] == 80 and isinstance(feats["dst_port"], int)
    assert feats["iat_max"] == pytest.approx(0.012)
    assert "label" not in feats


def test_csv_replay_skips_bad_rows_and_honours_limit(tmp_path):
    bad_nan = list(GOOD)
    bad_nan[1] = "nan"
    bad_text = list(GOOD)
    bad_text[0] = "abc"
    p = tmp_path / "flows.csv"
    p.write_text(csv_text([bad_nan, bad_text, GOOD, GOOD, GOOD]))
    out = []
    assert replay_csv(str(p), out.append, delay=0, limit=2) == 2


def test_csv_replay_strips_header_whitespace_and_reads_ips(tmp_path):
    header = [" " + c for c in FEATURE_ORDER] + ["src_ip", "dst_ip"]
    p = tmp_path / "flows.csv"
    p.write_text(",".join(header) + "\n" + ",".join(str(v) for v in GOOD + ["1.2.3.4", "5.6.7.8"]) + "\n")
    out = []
    assert replay_csv(str(p), out.append, delay=0) == 1
    assert (out[0]["src_ip"], out[0]["dst_ip"]) == ("1.2.3.4", "5.6.7.8")


def test_csv_missing_columns_is_a_clear_error(tmp_path):
    p = tmp_path / "flows.csv"
    p.write_text("dst_port,flow_duration_s\n80,1.0\n")
    with pytest.raises(ValueError, match="missing feature columns"):
        replay_csv(str(p), lambda x: None, delay=0)


def test_pcap_replay_matches_live_pipeline(tmp_path):
    pytest.importorskip("scapy")
    from scapy.all import IP, TCP, UDP, Ether, wrpcap

    def tcp(src, sport, dst, dport, flags, ts):
        p = Ether() / IP(src=src, dst=dst) / TCP(sport=sport, dport=dport, flags=flags)
        p.time = ts
        return p

    udp = Ether() / IP(src="10.0.0.9", dst="8.8.8.8") / UDP(sport=5000, dport=53) / b"query"
    udp.time = 1050.0
    pkts = [
        tcp("10.0.0.1", 40000, "10.0.0.2", 80, "S", 1000.0),
        tcp("10.0.0.2", 80, "10.0.0.1", 40000, "SA", 1000.1),
        tcp("10.0.0.1", 40000, "10.0.0.2", 80, "A", 1000.3),
        udp,
    ]
    path = tmp_path / "t.pcap"
    wrpcap(str(path), pkts)

    out = []
    n = replay_pcap(str(path), out.append)
    assert n == 2
    by_port = {p["dst_port"]: p for p in out}
    hs = by_port[80]["features"]
    assert hs["fwd_packets"] == 2 and hs["bwd_packets"] == 1
    assert hs["syn_count"] == 2 and hs["ack_count"] == 2
    assert hs["flow_duration_s"] == pytest.approx(0.3, abs=1e-3)
    assert hs["pkt_len_max"] == 40
    dns = by_port[53]["features"]
    assert dns["fwd_packets"] == 1 and dns["bwd_packets"] == 0
    assert dns["flow_duration_s"] == 0.0 and dns["packets_per_sec"] == 0.0