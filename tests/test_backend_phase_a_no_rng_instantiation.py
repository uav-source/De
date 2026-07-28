from backend_phase_a_test_support import ROOT, artifact_json, protocol


def test_plan_enumeration_has_no_rng_or_scene_generation_boundary():
    source = (ROOT / "src/zero_perturbation/backend_phase_a_protocol.py").read_text()
    prepare = (ROOT / "scripts/166_prepare_backend_phase_a_lock.py").read_text()
    assert "np.random" not in source
    assert "numpy.random" not in source
    assert "day2_development_scene" not in source
    assert "from capture_range" not in prepare
    assert len(tuple(protocol().planned_snapshots())) == 210
    audit = artifact_json("seed_usage_audit.json")
    assert audit["PHASE_A_RNG_INSTANTIATION_COUNT"] == 0
    assert audit["scene_generator_imported_or_called"] is False
