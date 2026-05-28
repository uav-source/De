from pathlib import Path

import numpy as np
import yaml

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from degen_detector.odi_tracker import compute_metrics_for_sequence  # noqa: E402
from degen_detector.weak_direction import (  # noqa: E402
    compute_axis_alignment,
    compute_drift_alignment,
    extract_weak_subspace,
    get_primary_weak_direction,
    is_direction_reliable,
    translation_component,
)
from degen_detector.whitened_info import eigen_decompose  # noqa: E402


def load_config():
    with (ROOT / "configs/detector/odi_default.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_obs(day14_tmp_pipeline, sequence_id):
    return np.load(day14_tmp_pipeline["seq"](sequence_id) / "observations.npz")


def test_weak_direction_contract_uses_translation_component_only():
    text = (ROOT / "docs/formula_contract.md").read_text(encoding="utf-8")

    assert "V_W = {v_i | lambda_i / lambda_1 < tau_w}" in text
    assert "v_p = normalize(v_weak[3:6])" in text
    assert "axis_alignment = |v_p^T a|" in text
    assert "unreliable" in text


def test_artificial_H_extracts_x_translation_as_weak_direction():
    H = np.diag([100.0, 90.0, 80.0, 1.0e-9, 70.0, 60.0])
    eigvals, eigvecs = eigen_decompose(H)

    weak = get_primary_weak_direction(eigvals, eigvecs)
    weak_trans = translation_component(weak)
    weak_subspace = extract_weak_subspace(eigvals, eigvecs, tau_w=0.02)

    assert compute_axis_alignment(weak_trans, np.array([1.0, 0.0, 0.0])) > 0.999
    assert weak_subspace.shape[1] == 1
    assert is_direction_reliable(eigvals, eigvecs, min_gap_ratio=1.0e-3, min_translation_norm=0.25)


def test_isotropic_H_is_unreliable():
    H = np.eye(6)
    eigvals, eigvecs = eigen_decompose(H)

    assert not is_direction_reliable(eigvals, eigvecs, min_gap_ratio=1.0e-3, min_translation_norm=0.25)


def test_eigenvector_sign_does_not_change_alignment():
    assert compute_axis_alignment(np.array([1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0])) == 1.0
    assert compute_axis_alignment(np.array([-1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0])) == 1.0
    assert compute_drift_alignment(np.array([-1.0, 0.0, 0.0]), np.array([3.0, 0.0, 0.0])) == 1.0


def test_st_median_axis_alignment_passes_day14_gate(day14_tmp_pipeline):
    rows = compute_metrics_for_sequence(load_obs(day14_tmp_pipeline, "ST-L3-S01-M1"), load_config())
    reliable = rows["weak_reliable"].astype(bool)

    assert float(np.mean(reliable)) > 0.95
    assert float(np.median(rows["axis_alignment"][reliable])) >= 0.70


def test_rt_median_axis_alignment_passes_day14_gate(day14_tmp_pipeline):
    rows = compute_metrics_for_sequence(load_obs(day14_tmp_pipeline, "RT-L4-S01-M1"), load_config())
    reliable = rows["weak_reliable"].astype(bool)

    assert float(np.mean(reliable)) > 0.95
    assert float(np.median(rows["axis_alignment"][reliable])) >= 0.70


def test_oc_reliable_frame_ratio_is_not_high(day14_tmp_pipeline):
    rows = compute_metrics_for_sequence(load_obs(day14_tmp_pipeline, "OC-L0-S01-M1"), load_config())

    assert float(np.mean(rows["weak_reliable"])) < 0.20


def test_ct_axis_alignment_uses_local_axis_not_fixed_global_x(day14_tmp_pipeline):
    obs = load_obs(day14_tmp_pipeline, "CT-L2-S01-M2")
    rows = compute_metrics_for_sequence(obs, load_config())
    reliable = rows["weak_reliable"].astype(bool)
    weak_trans = np.column_stack(
        [rows["weak_trans_x"], rows["weak_trans_y"], rows["weak_trans_z"]]
    )[reliable]
    local_axis = obs["axis_per_frame"][reliable]
    local_alignment = np.abs(np.einsum("ij,ij->i", weak_trans, local_axis))
    fixed_global_x_alignment = np.abs(weak_trans[:, 0])

    assert float(np.mean(reliable)) > 0.95
    assert float(np.median(local_alignment)) >= 0.70
    assert float(np.std(fixed_global_x_alignment)) > 0.05
    assert not np.allclose(local_alignment, fixed_global_x_alignment)
