from pathlib import Path

from zero_perturbation.phase_a_scientific_lock_v2 import (
    expected_scientific_payload,
    scientific_projection_diff,
)


ROOT = Path(__file__).resolve().parents[1]


def test_scientific_projection_is_zero_difference() -> None:
    result = scientific_projection_diff(expected_scientific_payload(ROOT), root=ROOT)
    assert result["SCIENTIFIC_PROTOCOL_PROJECTION_PASS"] is True
    assert all(value == 0 for key, value in result.items() if key.endswith("count") or key.endswith("difference"))

