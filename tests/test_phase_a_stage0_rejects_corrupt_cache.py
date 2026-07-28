import pytest

from backend_phase_a_v1_2_test_support import synthetic_snapshot
from zero_perturbation.backend_phase_a_v1_2 import CorruptSnapshotCache, snapshot_directory, write_snapshot_atomic


def test_stage0_resume_rejects_corrupt_array_file(tmp_path):
    snapshot = synthetic_snapshot()
    write_snapshot_atomic(tmp_path, snapshot, resume=False)
    path = snapshot_directory(tmp_path, snapshot.metadata["snapshot_id"]) / "source_points.npy"
    path.write_bytes(path.read_bytes()[:-1] + b"X")
    with pytest.raises(CorruptSnapshotCache, match="file SHA"):
        write_snapshot_atomic(tmp_path, snapshot, resume=True)
