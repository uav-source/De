from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.synthetic_pipeline_common import aggregate_process_trial_rows  # noqa: E402


def test_five_process_trials_produce_one_independent_sensor_row():
    rows = [
        {
            "sequence_id": "ST-L2-G01",
            "sensor_seed": 11,
            "process_seed": 1001 + index,
            "axis_drift_rate": 0.1 + 0.01 * index,
            "final_axis_error": 1.0 + index,
        }
        for index in range(5)
    ]
    aggregated = aggregate_process_trial_rows(rows)
    assert len(aggregated) == 1
    assert aggregated[("ST-L2-G01", 11)]["process_trial_count"] == 5
