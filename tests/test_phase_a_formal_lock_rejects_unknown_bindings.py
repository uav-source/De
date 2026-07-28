import copy

import pytest

from phase_a_formal_lock_test_support import make_valid_formal_lock, rewrite_payload_sha, validate_case, write_json
from zero_perturbation.phase_a_formal_execution_lock_schema import FormalExecutionLockValidationError


def test_formal_lock_rejects_unknown_binding(tmp_path):
    case = make_valid_formal_lock(tmp_path)
    value = copy.deepcopy(case.value)
    value["implementation_bindings"]["legacy_runner_sha256"] = "0" * 64
    rewrite_payload_sha(value)
    path = tmp_path / "unknown-binding.json"
    write_json(path, value)
    with pytest.raises(FormalExecutionLockValidationError, match="unknown fields"):
        validate_case(case, path)
