from fastlio2_adapter.measurement_mode import (
    MeasurementModeProcessor,
    deterministic_payload,
)
from test_runtime_observation_v3 import v3_record


def test_frozen_observation_produces_identical_measurement_science_fields():
    processor = MeasurementModeProcessor()
    outputs = [deterministic_payload(processor.process(v3_record())) for _ in range(3)]
    assert outputs[0] == outputs[1] == outputs[2]
    assert processor.same_call_mutation_count == 0

