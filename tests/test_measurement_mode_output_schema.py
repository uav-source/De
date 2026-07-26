import math

import pytest

from fastlio2_adapter.measurement_mode import (
    MEASUREMENT_FIELDS,
    MeasurementModeProcessor,
    validate_measurement_row,
)
from test_runtime_observation_v3 import v3_record


def test_measurement_mode_retains_exact_minimal_scalar_schema():
    row = MeasurementModeProcessor().process(v3_record())
    assert tuple(row) == MEASUREMENT_FIELDS
    assert row["detector_valid"] is True
    assert row["residual_count"] == row["valid_correspondence_count"]
    assert row["lambda_min_trans"] <= row["lambda_mid_trans"]
    assert row["lambda_mid_trans"] <= row["lambda_max_trans"]
    assert sum(
        row[name]
        for name in (
            "normalized_eigenvalue_min",
            "normalized_eigenvalue_mid",
            "normalized_eigenvalue_max",
        )
    ) == pytest.approx(1.0)
    assert row["spectral_entropy_trans"] == pytest.approx(
        math.log(row["effective_rank_trans"])
    )
    validate_measurement_row(row)


def test_measurement_output_has_no_large_observation_arrays():
    row = MeasurementModeProcessor().process(v3_record())
    assert all(not isinstance(value, (list, dict)) for value in row.values())
    assert "jacobian" not in " ".join(row).lower()
    assert "correspondence_indices" not in row

