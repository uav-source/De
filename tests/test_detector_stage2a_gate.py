from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.detector_stage2a import (  # noqa: E402
    authorization_decisions,
    detector_gate_pass,
    direction_gate_pass,
)
from eval.synthetic_pipeline_common import load_yaml  # noqa: E402


def common():
    return load_yaml(ROOT / "configs/redesign/detector_stage2a_common.yaml")


def test_frozen_detector_and_direction_gate_boundaries_pass():
    detector = {
        "spearman_rho": 0.75,
        "bootstrap_ci_low": 1.0e-6,
        "median_per_geometry_kendall_tau": 0.67,
        "positive_direction_geometry_ratio": 0.80,
        "paired_monotonic_rate": 0.75,
    }
    direction = {
        "sweep_type": "geometry",
        "primary_direction_axis_alignment_median": 0.95,
        "primary_direction_axis_alignment_p10": 0.80,
        "primary_direction_stable_rate": 0.85,
        "actionable_direction_rate": 0.85,
        "L4_trigger_rate": 0.90,
        "L3_trigger_rate": 0.75,
    }
    assert detector_gate_pass(detector, common())
    assert direction_gate_pass(direction, common())


def test_any_gate_failure_withholds_weak_update_and_never_authorizes_risk():
    gates = {
        "engineering": "ENGINEERING_PASS",
        "geometry_mechanism": "GEOMETRY_MECHANISM_PASS",
        "observation_mechanism": "OBSERVATION_MECHANISM_PASS",
        "detector": "DETECTOR_FAIL",
    }
    decisions = authorization_decisions(gates)
    assert decisions["WEAK_UPDATE_AUTHORIZED"] is False
    assert decisions["RISK_WARNING_AUTHORIZED"] is False
