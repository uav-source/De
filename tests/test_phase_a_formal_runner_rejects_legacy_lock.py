import json

import pytest

from phase_a_formal_lock_test_support import ROOT
from zero_perturbation.phase_a_formal_execution_lock_schema import (
    FormalExecutionLockValidationError,
    PROTOCOL_LOCK_RELATIVE_PATH,
    SNAPSHOT_LOCK_RELATIVE_PATH,
    validate_phase_a_formal_execution_lock_strict,
)


def test_formal_runner_rejects_v1_legacy_execution_lock(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"schema_version": "phase_a_stage1_execution_lock_v1"}))
    with pytest.raises(FormalExecutionLockValidationError, match="legacy or unknown"):
        validate_phase_a_formal_execution_lock_strict(
            path,
            root=ROOT,
            protocol_lock=ROOT / PROTOCOL_LOCK_RELATIVE_PATH,
            snapshot_lock=ROOT / SNAPSHOT_LOCK_RELATIVE_PATH,
        )
