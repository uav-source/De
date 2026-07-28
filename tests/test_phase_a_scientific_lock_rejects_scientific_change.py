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


def test_scientific_lock_rejects_changed_scene() -> None:
    value = deepcopy(expected_scientific_payload(ROOT))
    value["scenes"][0] = "CHANGED"
    value.pop("scientific_payload_sha256")
    value["scientific_payload_sha256"] = canonical_json_sha256(value)
    with pytest.raises(ScientificLockError, match="frozen projection changed"):
        validate_scientific_lock(value, root=ROOT)

