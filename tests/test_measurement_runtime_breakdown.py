import csv

import pytest

from fastlio2_adapter.measurement_mode import (
    MeasurementModeProcessor,
    write_measurement_csv,
)
from test_runtime_observation_v3 import v3_record


def test_capture_detector_and_logging_times_are_separate(tmp_path):
    processor = MeasurementModeProcessor()
    row = processor.process(
        v3_record(),
        runtime={"tap_capture_ns": 2_500_000, "binary_writer_ns": 750_000},
    )
    assert row["capture_core_ms"] == 2.5
    assert row["logging_ms"] == 0.75
    assert row["detector_core_ms"] >= 0.0
    output = tmp_path / "frame_metrics.csv"
    write_measurement_csv(output, [row])
    assert row["logging_ms"] >= 0.75
    assert row["total_added_ms"] == pytest.approx(
        row["capture_core_ms"]
        + row["detector_core_ms"]
        + row["logging_ms"]
    )
    with output.open(newline="", encoding="utf-8") as handle:
        written = next(csv.DictReader(handle))
    assert float(written["capture_core_ms"]) == 2.5
    assert float(written["logging_ms"]) >= 0.75

