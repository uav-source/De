from phase_a_execution_chain_test_support import ROOT, actual_execution_chain


def test_audit_records_zero_formal_seed_access(actual_execution_chain):
    assert actual_execution_chain["manifest"]["FORMAL_PHASE_A_SEED_ACCESS_COUNT"] == 0
    source = (ROOT / "src/zero_perturbation/phase_a_execution_chain_audit.py").read_text()
    assert "load_backend_phase_a_protocol" not in source
    parameter_lock = (ROOT / "tests/data/phase_a_execution_chain_audit/fixture_backend_parameter_lock.json").read_text()
    assert "geometry_seed" not in parameter_lock
    assert "measurement_seed" not in parameter_lock
