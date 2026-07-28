import json
import pytest

from backend_phase_a_v1_2_test_support import ROOT
from zero_perturbation.backend_phase_a_v1_2 import Stage0ContractError, validate_snapshot_lock


def test_stage1_runner_rejects_invalid_snapshot_lock_before_execution(tmp_path):
    path = tmp_path / "snapshot-lock.json"
    path.write_text(json.dumps({"schema_version": "wrong"}), encoding="utf-8")
    with pytest.raises(Stage0ContractError, match="unknown or invalid"):
        validate_snapshot_lock(path, ROOT)
