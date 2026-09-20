import os
import sys

def test_project_setup():
    required_dirs = ['ml', 'api', 'capture', 'dashboard', 'data', 'docs']
    for d in required_dirs:
        assert os.path.isdir(d), f"Directory missing: {d}"

    assert os.path.isfile("AGENTS.md"), "AGENTS.md is missing"
    assert os.path.isfile(".gitignore"), ".gitignore is missing"
    assert os.path.isfile("requirements.txt"), "requirements.txt is missing"
    assert os.path.isdir("venv"), "venv directory missing"

    with open("AGENTS.md", "r", encoding="utf-8") as f:
        content = f.read()

    expected_features = [
        "dst_port", "flow_duration_s", "fwd_packets", "bwd_packets",
        "fwd_bytes", "bwd_bytes", "bytes_per_sec", "packets_per_sec",
        "pkt_len_mean", "pkt_len_std", "pkt_len_max", "pkt_len_min",
        "syn_count", "ack_count", "fin_count", "rst_count",
        "psh_count", "iat_mean", "iat_max"
    ]

    last_idx = -1
    for feat in expected_features:
        idx = content.find(f"`{feat}`")
        assert idx != -1, f"Feature {feat} not found in AGENTS.md"
        assert idx > last_idx, f"Feature {feat} is not in specified order in AGENTS.md"
        last_idx = idx

    print("Setup validation successful: All directories, contracts, gitignore, and venv verified.")

if __name__ == "__main__":
    test_project_setup()
