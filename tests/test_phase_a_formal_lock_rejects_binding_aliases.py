import copy

import pytest

from phase_a_formal_lock_test_support import make_valid_formal_lock, rewrite_payload_sha, validate_case, write_json
from zero_perturbation.phase_a_formal_execution_lock_schema import FormalExecutionLockValidationError


@pytest.mark.parametrize("canonical,alias", [("publisher_sha256", "publisher"), ("independent_verifier_sha256", "verifier_sha256")])
def test_formal_lock_rejects_binding_aliases(tmp_path, canonical, alias):
    case = make_valid_formal_lock(tmp_path)
    value = copy.deepcopy(case.value)
    value["implementation_bindings"][alias] = value["implementation_bindings"].pop(canonical)
    rewrite_payload_sha(value)
    path = tmp_path / f"alias-{alias}.json"
    write_json(path, value)
    with pytest.raises(FormalExecutionLockValidationError):
        validate_case(case, path)
