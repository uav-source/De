from copy import deepcopy
from pathlib import Path

import pytest

from zero_perturbation.phase_a_scientific_lock_v2 import (
    ScientificLockError,
    expected_scientific_payload,
    validate_scientific_lock,
)
from zero_perturbation.phase_a_trial_result_schema import canonical_json_sha256


ROOT = Path(__file__).resolve().parents[1]


def test_scientific_lock_rejects_runner_sha() -> None:
    value = deepcopy(expected_scientific_payload(ROOT))
    value.pop("scientific_payload_sha256")
    value["runner_sha256"] = "0" * 64
    value["scientific_payload_sha256"] = canonical_json_sha256(value)
    with pytest.raises(ScientificLockError):
        validate_scientific_lock(value, root=ROOT)

