from pathlib import Path
from typing import Dict

import numpy as np
import yaml

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from degen_detector.odi_tracker import (  # noqa: E402
    compute_ODI,
    compute_effective_rank,
    compute_metrics_for_frame,
    compute_metrics_for_sequence,
)


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
    assert config["weak_min_gap_ratio"] == "1.0e-3"
    assert config["weak_min_translation_norm"] == "0.25"
    assert config["window_size"] == "20"
    assert config["window_stride"] == "5"
    assert config["random_seed"] == "42"


def load_config():
    with (ROOT / "configs/detector/odi_default.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_obs(day14_tmp_pipeline, sequence_id):
    return np.load(day14_tmp_pipeline["seq"](sequence_id) / "observations.npz")


def test_isotropic_eigenvalues_have_low_ODI():
    eigvals = np.ones(6)

    assert compute_effective_rank(eigvals, 1.0e-9) > 5.99
    assert compute_ODI(eigvals, 1.0e-9) < 1.0e-6


def test_rank_one_dominant_spectrum_has_high_ODI():
    eigvals = np.array([1.0e6, 1.0, 1.0, 1.0, 1.0, 1.0])

    assert compute_ODI(eigvals, 1.0e-9) > 0.95


def test_condition_number_can_explode_but_ODI_remains_finite():
    eigvals = np.array([1.0, 0.5, 0.25, 0.1, 0.01, 1.0e-18])

    odi = compute_ODI(eigvals, 1.0e-12)

    assert np.isfinite(odi)
    assert 0.0 <= odi <= 1.0


def test_compute_metrics_for_frame_outputs_required_fields(day14_tmp_pipeline):
    obs = load_obs(day14_tmp_pipeline, "ST-L3-S01-M1")
    config = load_config()

    metrics = compute_metrics_for_frame(obs["packed_J"][0], obs["R_diag_list"][0], config)

    for key in ["ODI", "AIS", "lambda_min", "condition_number", "num_points"]:
        assert key in metrics
        assert np.isfinite(metrics[key])
    for idx in range(1, 7):
        assert f"eig_{idx}" in metrics


def test_compute_metrics_for_sequence_outputs_required_dtype_fields(day14_tmp_pipeline):
    obs = load_obs(day14_tmp_pipeline, "OC-L0-S01-M1")
    rows = compute_metrics_for_sequence(obs, load_config())

    assert rows.shape[0] == obs["packed_J"].shape[0]
    for key in ["timestamp", "eig_1", "eig_6", "ODI", "AIS", "lambda_min", "condition_number", "num_points"]:
        assert key in rows.dtype.names


def test_st_rt_odi_higher_than_open_control(day14_tmp_pipeline):
    config = load_config()
    oc = compute_metrics_for_sequence(load_obs(day14_tmp_pipeline, "OC-L0-S01-M1"), config)
    st = compute_metrics_for_sequence(load_obs(day14_tmp_pipeline, "ST-L3-S01-M1"), config)
    rt = compute_metrics_for_sequence(load_obs(day14_tmp_pipeline, "RT-L4-S01-M1"), config)

    assert float(np.median(st["ODI"])) > float(np.median(oc["ODI"])) + 0.10
    assert float(np.median(rt["ODI"])) > float(np.median(oc["ODI"])) + 0.10


def test_ct_odi_not_identical_to_st_global_pattern(day14_tmp_pipeline):
    config = load_config()
    st = compute_metrics_for_sequence(load_obs(day14_tmp_pipeline, "ST-L3-S01-M1"), config)
    ct = compute_metrics_for_sequence(load_obs(day14_tmp_pipeline, "CT-L2-S01-M2"), config)

    assert not np.allclose(ct["eig_1"][:50], st["eig_1"][:50])
    assert np.std(ct["eig_1"]) > 1.0
