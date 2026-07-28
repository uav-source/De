import copy

import pytest

from phase_a_formal_lock_test_support import make_valid_formal_lock, rewrite_payload_sha, validate_case, write_json
from zero_perturbation.phase_a_formal_execution_lock_schema import FormalExecutionLockValidationError


WRONG_SHA_BINDINGS = (
    "publisher_sha256",
    "independent_verifier_sha256",
    "formal_runner_sha256",
    "trial_result_schema_sha256",
    "trial_result_writer_sha256",
    "trial_resume_validator_sha256",
    "stage1_analysis_sha256",
    "artifact_verifier_sha256",
    "open3d_adapter_sha256",
    "pcl_adapter_sha256",
    "pcl_cli_sha256",
    "rotation_metric_sha256",
)


@pytest.mark.parametrize("binding", WRONG_SHA_BINDINGS)
def test_each_wrong_implementation_binding_sha_is_rejected(tmp_path, binding):
    case = make_valid_formal_lock(tmp_path)
    value = copy.deepcopy(case.value)
    value["implementation_bindings"][binding] = "0" * 64
    rewrite_payload_sha(value)
    path = tmp_path / f"wrong-{binding}.json"
    write_json(path, value)
    with pytest.raises(FormalExecutionLockValidationError, match="FORMAL_LOCK_IMPLEMENTATION_BINDING_MISMATCH"):
        validate_case(case, path)
