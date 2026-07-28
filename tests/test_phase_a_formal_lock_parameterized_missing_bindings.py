import copy

import pytest

from phase_a_formal_lock_test_support import make_valid_formal_lock, rewrite_payload_sha, validate_case, write_json
from zero_perturbation.phase_a_formal_execution_lock_schema import (
    FormalExecutionLockValidationError,
    IMPLEMENTATION_BINDING_FIELDS,
)


@pytest.mark.parametrize("binding", sorted(IMPLEMENTATION_BINDING_FIELDS))
def test_every_missing_implementation_binding_is_rejected(tmp_path, binding):
    case = make_valid_formal_lock(tmp_path)
    altered = copy.deepcopy(case.value)
    del altered["implementation_bindings"][binding]
    rewrite_payload_sha(altered)
    path = tmp_path / f"missing-{binding}.json"
    write_json(path, altered)
    with pytest.raises(FormalExecutionLockValidationError, match="FORMAL_LOCK_MISSING_REQUIRED_BINDING"):
        validate_case(case, path)
