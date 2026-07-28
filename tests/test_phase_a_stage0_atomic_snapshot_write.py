from backend_phase_a_v1_2_test_support import synthetic_snapshot
from zero_perturbation.backend_phase_a_v1_2 import snapshot_directory, write_snapshot_atomic


def test_stage0_snapshot_write_is_complete_after_atomic_rename(tmp_path):
    snapshot = synthetic_snapshot()
    metadata, reused = write_snapshot_atomic(tmp_path, snapshot, resume=False)
    directory = snapshot_directory(tmp_path, snapshot.metadata["snapshot_id"])
    assert reused is False
    assert metadata["snapshot_id"] == snapshot.metadata["snapshot_id"]
    assert {path.name for path in directory.iterdir()} == {"source_points.npy", "target_points.npy", "reference_pose.npy", "source_parent_target_indices.npy", "metadata.json"}
    assert not list(tmp_path.rglob("*.tmp"))
