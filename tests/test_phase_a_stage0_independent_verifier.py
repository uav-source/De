import inspect

from zero_perturbation import backend_phase_a_stage0_verification as verifier


def test_independent_verifier_does_not_import_or_call_stage0_builder():
    source = inspect.getsource(verifier)
    assert "backend_phase_a_v1_2 import" not in source
    assert "build_canonical_snapshot" not in source
    assert "build_stage0_cache" not in source
