import hashlib
import json
from pathlib import Path

from eval import stage2_failure_day13 as day13_v1
from eval.stage2_failure_day13_correction_schema import validate_output_directory
from eval.stage2_failure_day13_correction_v2 import run_day13_analysis_correction_v2


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "results/stage2_failure_analysis/day13_new_seed/"
    "stage2_failure_day13_new_seed_v1"
)
FROZEN = (
    "calibration/frame_scores.csv",
    "evaluation/frame_scores.csv",
    "evaluation/frames_merged.csv",
    "evaluation/auroc_summary.csv",
    "evaluation/primary_roc_points.csv",
    "evaluation/fpr_summary.csv",
    "evaluation/preliminary_criteria_summary.json",
    "day13_summary.json",
)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_v1_pipeline_regression_and_no_estimator(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("V2 invoked a forbidden V1 experiment function")

    monkeypatch.setattr(day13_v1, "run_map_lio", forbidden)
    monkeypatch.setattr(day13_v1, "run_day13_calibration", forbidden)
    monkeypatch.setattr(day13_v1, "run_day13_evaluation", forbidden)
    before = {name: _sha(SOURCE / name) for name in FROZEN}
    output = tmp_path / "v2"
    result = run_day13_analysis_correction_v2(ROOT, SOURCE, output)
    after = {name: _sha(SOURCE / name) for name in FROZEN}
    assert before == after
    validate_output_directory(output)

    manifest = result["manifest"]
    assert manifest["corrected_geometry_positive_count"] == 1600
    assert manifest["corrected_geometry_negative_count"] == 1600
    assert manifest["corrected_observation_positive_count"] == 1600
    assert manifest["corrected_observation_negative_count"] == 1600
    assert abs(manifest["corrected_geometry_auroc"] - 0.59932578125) <= 1e-12
    assert abs(manifest["corrected_geometry_ci95_lower"] - 0.5514198632812499) <= 1e-10
    assert abs(manifest["corrected_geometry_ci95_upper"] - 0.6363024804687499) <= 1e-10
    assert abs(manifest["corrected_observation_auroc"] - 0.686236328125) <= 1e-12
    assert abs(manifest["corrected_observation_ci95_lower"] - 0.6432498046874999) <= 1e-10
    assert abs(manifest["corrected_observation_ci95_upper"] - 0.7287901953125) <= 1e-10
    assert manifest["geometry_locked_threshold_tpr"] == 0.14625
    assert manifest["geometry_matched_clean_fpr"] == 0.091875
    assert manifest["observation_locked_threshold_tpr"] == 0.223125
    assert manifest["observation_matched_clean_fpr"] == 0.07875
    assert manifest["clean_fpr_target_status"] == "MIXED_POPULATION_DEPENDENT"
    assert manifest["DAY13_CORRECTION_PASS"] is True
    assert manifest["DAY14_STAGE2_DECISION_AUTHORIZED"] is True
    assert manifest["STAGE2_GATE"] == "INCOMPLETE"
    assert manifest["estimator_invoked"] is False
    assert not any((output / name).exists() for name in (
        "frame_scores.csv", "frames_merged.csv", "frames_online.csv",
        "frames_gt.csv", "frames_window.csv",
    ))
