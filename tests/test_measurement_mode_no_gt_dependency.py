import pytest

from fastlio2_adapter.measurement_mode import (
    MeasurementModeError,
    MeasurementModeProcessor,
)
from test_runtime_observation_v3 import v3_record


def test_measurement_mode_rejects_offline_reference_payloads():
    observation = v3_record()
    observation["navsat_fix"] = {"latitude": 47.0, "longitude": -52.0}
    processor = MeasurementModeProcessor()
    with pytest.raises(MeasurementModeError, match="offline reference"):
        processor.process(observation)
    assert processor.reference_input_access_count == 0


def test_detector_output_requires_only_readonly_fastlio_observation():
    processor = MeasurementModeProcessor()
    row = processor.process(v3_record())
    assert row["detector_valid"] is True
    assert processor.reference_input_access_count == 0

