import pytest

from backend_phase_a_v1_1_test_support import ROOT, write_valid_lock
from zero_perturbation.backend_phase_a_v1_1 import (
    dry_run,
    validate_v1_1_lock_document,
)


def test_runner_requires_valid_v1_1_lock(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_v1_1_lock_document(tmp_path / "missing.json", ROOT)
    lock = tmp_path / "lock.json"
    write_valid_lock(lock)
    report = dry_run(
        root=ROOT,
        protocol_lock=lock,
        run_id="fixture-dry-run",
        output_dir=tmp_path / "never-created",
        workers=2,
    )
    assert report["dry_run_pass"] is True

