import json
import pytest

from backend_phase_a_v1_2_test_support import synthetic_snapshot
from zero_perturbation.backend_phase_a_v1_2 import CorruptSnapshotCache, snapshot_directory, write_snapshot_atomic


def test_stage0_resume_rejects_tampered_metadata(tmp_path):
    snapshot = synthetic_snapshot()
    write_snapshot_atomic(tmp_path, snapshot, resume=False)
    path = snapshot_directory(tmp_path, snapshot.metadata["snapshot_id"]) / "metadata.json"
    value = json.loads(path.read_text())
    value["repeat_index"] = 999
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(CorruptSnapshotCache, match="metadata payload SHA"):
        write_snapshot_atomic(tmp_path, snapshot, resume=True)
