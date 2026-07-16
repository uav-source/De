import pytest

from eval.stage2_failure_day13_statistics import calibrate_diagnostic_threshold


def _row(role="calibration", stress="clean", score=1.0):
    return {"role": role, "stress": stress, "stat_input_valid": True, "window_ready": True, "primary_score": score}


def test_calibration_rejects_evaluation_and_nonclean_scores():
    with pytest.raises(ValueError):
        calibrate_diagnostic_threshold([_row(role="evaluation")])
    with pytest.raises(ValueError):
        calibrate_diagnostic_threshold([_row(stress="coherent_subhuber_slip")])
    with pytest.raises(ValueError):
        calibrate_diagnostic_threshold([{**_row(), "pose_gt": [1, 2, 3]}])
