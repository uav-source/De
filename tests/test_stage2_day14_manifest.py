from eval.stage2_day14_schema import (
    DAY14_SCHEMA_VERSION,
    evaluate_day14_completion,
    load_day14_config,
)
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_config_and_engineering_pass_do_not_imply_scientific_pass():
    config = load_day14_config(ROOT / "configs/stage2/day14_decision.yaml")
    assert config["locked_primary_statistic"] == "huber_cusum_max"
    assert config["locked_threshold"] == 13.745952939169019
    manifest = {
        "schema_version": DAY14_SCHEMA_VERSION,
        "worktree_clean": True, "missing_evidence_count": 0,
        "invalid_evidence_count": 0, "calibration_rerun": False,
        "evaluation_rerun": False, "reserved_test_rerun": False,
        "estimator_invoked": False, "retuning_performed": False,
        "new_statistic_added": False, "threshold_changed": False,
        "seed_changed": False, "stress_changed": False,
        "day13_v1_unchanged": True, "day13_v2_artifact_unchanged": True,
        "stage2b_artifact_unchanged": True, "stage2c_artifact_unchanged": True,
        "output_schema_pass": True, "STAGE2_GATE": "FAIL",
        "evidence_file_count": 20,
    }
    assert evaluate_day14_completion(manifest) is True
    assert manifest["STAGE2_GATE"] == "FAIL"

