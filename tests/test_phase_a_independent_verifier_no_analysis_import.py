from phase_a_execution_chain_test_support import ROOT


def test_independent_verifier_does_not_import_analyzer_or_publisher():
    source = (ROOT / "src/zero_perturbation/phase_a_stage1_independent_verifier.py").read_text()
    assert "phase_a_stage1_analysis" not in source
    assert "phase_a_stage1_publisher" not in source
