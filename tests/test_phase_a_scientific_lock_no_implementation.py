from pathlib import Path

from zero_perturbation.phase_a_scientific_lock_v2 import (
    expected_scientific_payload,
    scientific_lock_implementation_fields,
)


ROOT = Path(__file__).resolve().parents[1]


def test_scientific_lock_contains_no_implementation_fields() -> None:
    assert scientific_lock_implementation_fields(expected_scientific_payload(ROOT)) == []

