import json

import pytest

from backend_phase_a_v1_1_test_support import ROOT, write_valid_lock
from zero_perturbation.backend_phase_a_v1_1 import (
    RunnerContractError,
    validate_v1_1_lock_document,
)


def test_runner_rejects_tampered_v1_1_lock(tmp_path):
    path = tmp_path / "lock.json"
    document = write_valid_lock(path)
    document["formal_execution_authorized"] = False
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(RunnerContractError, match="payload SHA mismatch"):
        validate_v1_1_lock_document(path, ROOT)

