import copy
import json

import pytest

from phase_a_formal_lock_test_support import ROOT, make_valid_formal_lock, rewrite_payload_sha, validate_case, write_json
from zero_perturbation.phase_a_formal_execution_lock_schema import (
    FormalExecutionLockValidationError,
    PROTOCOL_LOCK_RELATIVE_PATH,
    SNAPSHOT_LOCK_RELATIVE_PATH,
    validate_phase_a_formal_execution_lock_strict,
)


@pytest.mark.parametrize(
    "relative",
    [
        "artifacts/current/zero_perturbation_backend_phase_a_v1_2_lock/backend_phase_a_v1_2_protocol_lock.json",
        "artifacts/current/zero_perturbation_backend_phase_a_v1_2_stage0/backend_phase_a_v1_2_snapshot_lock.json",
        "tests/data/phase_a_execution_chain_audit/fixture_snapshot_lock.json",
    ],
)
def test_non_execution_locks_are_rejected(tmp_path, relative):
    with pytest.raises(FormalExecutionLockValidationError):
        validate_phase_a_formal_execution_lock_strict(
            ROOT / relative,
            root=ROOT,
            protocol_lock=ROOT / PROTOCOL_LOCK_RELATIVE_PATH,
            snapshot_lock=ROOT / SNAPSHOT_LOCK_RELATIVE_PATH,
        )


@pytest.mark.parametrize("schema_version", ["phase_a_stage1_execution_lock_v1", "phase_a_stage1_execution_lock_v1_1"])
def test_legacy_execution_lock_versions_are_rejected(tmp_path, schema_version):
    path = tmp_path / f"{schema_version}.json"
    path.write_text(json.dumps({"schema_version": schema_version}))
    with pytest.raises(FormalExecutionLockValidationError):
        validate_phase_a_formal_execution_lock_strict(
            path,
            root=ROOT,
            protocol_lock=ROOT / PROTOCOL_LOCK_RELATIVE_PATH,
            snapshot_lock=ROOT / SNAPSHOT_LOCK_RELATIVE_PATH,
        )


@pytest.mark.parametrize(
    "mutation",
    ["not_authorized", "fixture_only", "unknown_top", "manifest_path_instead_of_bindings"],
)
def test_incomplete_or_relaxed_new_locks_are_rejected(tmp_path, mutation):
    case = make_valid_formal_lock(tmp_path)
    value = copy.deepcopy(case.value)
    if mutation == "not_authorized":
        value["formal_execution_authorized"] = False
    elif mutation == "fixture_only":
        value["fixture_only"] = True
    elif mutation == "unknown_top":
        value["compatibility_mode"] = True
    else:
        del value["implementation_bindings"]
        value["implementation_manifest_path"] = "current.json"
    rewrite_payload_sha(value)
    path = tmp_path / f"{mutation}.json"
    write_json(path, value)
    with pytest.raises(FormalExecutionLockValidationError):
        validate_case(case, path)
