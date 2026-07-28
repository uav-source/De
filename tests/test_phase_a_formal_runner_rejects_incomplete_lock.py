import copy

import pytest

from phase_a_formal_lock_test_support import make_valid_formal_lock, rewrite_payload_sha, validate_case, write_json
from zero_perturbation.phase_a_formal_execution_lock_schema import FormalExecutionLockValidationError


def test_formal_runner_rejects_lock_without_implementation_bindings(tmp_path):
    case = make_valid_formal_lock(tmp_path)
    value = copy.deepcopy(case.value)
    del value["implementation_bindings"]
    rewrite_payload_sha(value)
    path = tmp_path / "incomplete.json"
    write_json(path, value)
    with pytest.raises(FormalExecutionLockValidationError, match="FORMAL_LOCK_SCHEMA_INVALID"):
        validate_case(case, path)
