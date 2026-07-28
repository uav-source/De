from zero_perturbation.backend_phase_a_v1_1 import InfrastructureInterruption


def test_infrastructure_interruption_is_not_scientific_solver_failure():
    interruption = InfrastructureInterruption("host interruption")
    assert interruption.classification == "INFRASTRUCTURE_INTERRUPTION"
    assert interruption.classification != "SCIENTIFIC_SOLVER_FAILURE"

