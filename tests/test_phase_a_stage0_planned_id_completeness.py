from backend_phase_a_v1_2_test_support import ROOT, write_minimal_protocol_lock
from zero_perturbation.backend_phase_a_stage0_verification import verify_stage0_cache


def test_independent_verifier_reports_all_missing_planned_ids(tmp_path):
    lock = tmp_path / "lock.json"
    write_minimal_protocol_lock(lock)
    cache = tmp_path / "empty-cache"
    cache.mkdir()
    result = verify_stage0_cache(root=ROOT, protocol_lock=lock, cache_root=cache)
    assert result["planned_snapshot_count"] == 210
    assert result["missing_snapshot_count"] == 210
    assert result["verification_pass"] is False
