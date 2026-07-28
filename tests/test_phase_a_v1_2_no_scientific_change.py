from backend_phase_a_v1_2_test_support import ROOT
from zero_perturbation.backend_phase_a_protocol import load_backend_phase_a_protocol
from zero_perturbation.backend_phase_a_v1_2 import load_v1_2_protocol


def test_v1_2_inherits_every_frozen_scientific_section():
    amendment = load_v1_2_protocol(ROOT)
    base = load_backend_phase_a_protocol(ROOT)
    names = amendment["scientific_contract"]["inherited_byte_exact_sections"]
    assert all(name in base.data for name in names)
    assert len(list(base.planned_snapshots())) == 210
    assert len(list(base.planned_trials())) == 420
