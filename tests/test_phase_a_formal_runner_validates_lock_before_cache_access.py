import copy

import pytest

from phase_a_formal_lock_test_support import ROOT, make_valid_formal_lock, rewrite_payload_sha, write_json
from zero_perturbation import backend_phase_a_stage1 as runner
from zero_perturbation.phase_a_formal_execution_lock_schema import (
    FormalExecutionLockValidationError,
    PROTOCOL_LOCK_RELATIVE_PATH,
    SNAPSHOT_LOCK_RELATIVE_PATH,
)


def test_formal_runner_rejects_missing_binding_before_cache_access(tmp_path, monkeypatch):
    case = make_valid_formal_lock(tmp_path)
    value = copy.deepcopy(case.value)
    del value["implementation_bindings"]["publisher_sha256"]
    rewrite_payload_sha(value)
    bad_lock = tmp_path / "missing-publisher.json"
    write_json(bad_lock, value)
    cache_access_count = 0

    def forbidden_cache_access(*args, **kwargs):
        nonlocal cache_access_count
        cache_access_count += 1
        raise AssertionError("cache was accessed before strict lock rejection")

    monkeypatch.setattr(runner, "validate_snapshot_directory", forbidden_cache_access)
    with pytest.raises(FormalExecutionLockValidationError, match="FORMAL_LOCK_MISSING_REQUIRED_BINDING"):
        runner.dry_run_stage1(
            root=ROOT,
            protocol_lock=ROOT / PROTOCOL_LOCK_RELATIVE_PATH,
            snapshot_lock=ROOT / SNAPSHOT_LOCK_RELATIVE_PATH,
            formal_execution_lock=bad_lock,
            run_id="strict-order-test",
            output_dir=tmp_path,
            workers=1,
            implementation_manifest_path=case.manifest_path,
        )
    assert cache_access_count == 0
