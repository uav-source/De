from backend_phase_a_test_support import protocol


def test_phase_a_uses_only_the_frozen_development_seed_values():
    phase = protocol()
    assert phase.geometry_seeds == (1850310744, 1957656152, 1334931069)
    assert phase.measurement_seeds == (217775206, 1664898153)
    assert tuple(phase.development_seeds["geometry"].values()) == phase.geometry_seeds
    assert tuple(phase.development_seeds["measurement"].values()) == phase.measurement_seeds
    assert phase.repeats == (0, 1, 2, 3, 4)
