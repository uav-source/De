import copy

from fastlio2_adapter.measurement_mode import MeasurementModeProcessor
from test_runtime_observation_v3 import v3_record


def test_measurement_mode_preserves_raw_and_symmetric_covariance():
    observation = v3_record()
    raw_before = copy.deepcopy(
        observation["prior_covariance_detector_order_raw"]
    )
    symmetric_before = copy.deepcopy(
        observation["prior_covariance_detector_order_symmetric"]
    )
    processor = MeasurementModeProcessor()
    processor.process(observation)
    assert observation["prior_covariance_detector_order_raw"] == raw_before
    assert (
        observation["prior_covariance_detector_order_symmetric"]
        == symmetric_before
    )
    assert processor.covariance_write_count == 0

