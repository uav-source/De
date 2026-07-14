from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1b import aggregate_process_targets, merge_sensor_process_summaries  # noqa: E402


def test_thirty_process_trials_produce_one_sensor_summary_row():
    trials = []
    for index in range(30):
        value = (index - 14.5) / 100.0
        trials.append(
            {
                "sequence_id": "seq",
                "sensor_seed": 11,
                "final_axis_error_signed": value,
                "final_axis_error_abs": abs(value),
                "final_axis_error_squared": value**2,
                "axis_rmse": abs(value) / 2.0,
                "axis_mae": abs(value) / 3.0,
            }
        )
    aggregate = aggregate_process_targets(trials)
    assert aggregate["process_trial_count"] == 30
    rows = merge_sensor_process_summaries([{"sequence_id": "seq", "sensor_seed": 11}], trials, {})
    assert len(trials) == 30 and len(rows) == 1
    assert rows[0]["mean_final_axis_error_squared"] > 0.0
