from backend_qualification_test_support import ROOT, qualification_decision, qualification_protocol


def test_native_is_excluded_and_received_zero_qualification_trials():
    assert qualification_protocol()["backend_contract"]["excluded_backend"] == "native_full"
    assert qualification_decision()["native_qualification_trial_invocation_count"] == 0
    adapter = (ROOT / "src/zero_perturbation/pcl_backend.py").read_text()
    assert "from .native_backend" not in adapter

