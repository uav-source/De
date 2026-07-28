from backend_phase_a_v1_2_test_support import synthetic_snapshot
from zero_perturbation.backend_phase_a_v1_2 import write_snapshot_atomic


def test_stage0_resume_reuses_only_valid_identical_snapshot(tmp_path):
    snapshot = synthetic_snapshot()
    write_snapshot_atomic(tmp_path, snapshot, resume=False)
    metadata, reused = write_snapshot_atomic(tmp_path, snapshot, resume=True)
    assert reused is True
    assert metadata["snapshot_checksum"] == snapshot.metadata["snapshot_checksum"]
