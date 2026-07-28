import json
from pathlib import Path

import pytest

from zero_perturbation.backend_phase_a_v2 import LockValidationFailure, ValidationTrace, validate_lock_stack


ROOT = Path(__file__).resolve().parents[1]


def test_invalid_formal_lock_stops_before_cache(tmp_path: Path) -> None:
    lock = tmp_path / "bad.json"
    lock.write_text(json.dumps({"schema_version": "wrong"}))
    trace = ValidationTrace()
    with pytest.raises(LockValidationFailure):
        validate_lock_stack(root=ROOT, formal_run_lock=lock, trace=trace, require_environment=False)
    assert trace.cache_read_count == trace.formal_seed_access_count == trace.backend_execution_count == 0

