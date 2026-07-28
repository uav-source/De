import json

import pytest

from backend_phase_a_test_support import ARTIFACT, ROOT
from zero_perturbation.backend_phase_a_protocol import (
    validate_protocol_lock_document,
)


def test_phase_a_lock_rejects_missing_and_tampered_documents(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_protocol_lock_document(tmp_path / "missing.json", ROOT)
    lock = json.loads((ARTIFACT / "backend_phase_a_protocol_lock.json").read_text())
    lock["planned_trial_count"] = 419
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError, match="payload hash mismatch"):
        validate_protocol_lock_document(tampered, ROOT)
