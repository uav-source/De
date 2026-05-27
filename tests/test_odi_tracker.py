from pathlib import Path
from typing import Dict


ROOT = Path(__file__).resolve().parents[1]


def parse_simple_yaml(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def test_odi_default_config_freezes_required_keys():
    config = parse_simple_yaml(ROOT / "configs/detector/odi_default.yaml")

    assert config["s_theta"] == "0.05"
    assert config["s_p"] == "0.5"
    assert config["epsilon_mode"] == "relative_trace"
    assert config["epsilon_ratio"] == "1.0e-6"
    assert config["tau_w"] == "0.02"
    assert config["window_size"] == "20"
    assert config["window_stride"] == "5"
    assert config["random_seed"] == "42"
