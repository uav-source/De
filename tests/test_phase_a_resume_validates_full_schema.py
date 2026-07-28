import json

from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_trial_result_writer import write_phase_a_trial_result
from zero_perturbation.phase_a_trial_resume import validate_existing_trial_result_for_resume


def test_resume_accepts_only_a_manifest_hashed_strict_result(tmp_path):
    value = sample_result()
    path, digest = write_phase_a_trial_result(tmp_path, value)
    entry = {"path": path.name, "planned_trial_id": value["planned_trial_id"], "sha256": digest}
    expected = {name: value[name] for name in ("planned_trial_id", "snapshot_id", "backend", "scene_variant", "condition", "protocol_sha256", "snapshot_lock_sha256", "snapshot_checksum", "source_checksum", "target_checksum", "reference_pose_checksum", "implementation_sha256")}
    assert validate_existing_trial_result_for_resume(path, manifest_entry=entry, expected=expected) == value
