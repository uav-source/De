import copy

from fastlio2_adapter.measurement_mode import MeasurementModeProcessor
from test_runtime_observation_v3 import v3_record


def test_measurement_mode_never_writes_estimator_state():
    observation = v3_record()
    before = copy.deepcopy(observation)
    processor = MeasurementModeProcessor()
    processor.process(observation)
    assert observation == before
    assert processor.state_write_count == 0
    assert processor.detector_feedback_count == 0
    assert processor.same_call_mutation_count == 0

