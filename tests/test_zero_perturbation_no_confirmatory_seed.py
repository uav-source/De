from zero_perturbation.protocol import DevelopmentSeedFirewall
from zero_perturbation_test_support import development_protocol


def test_runtime_seed_mapping_contains_development_only():
    protocol = development_protocol()
    assert set(protocol.development_seeds) == {"geometry", "measurement", "bootstrap", "backend"}
    assert sum(len(values) for values in protocol.development_seeds.values()) == 8
    firewall = DevelopmentSeedFirewall(protocol)
    assert firewall.report()["CONFIRMATORY_SEED_INSTANTIATION_COUNT"] == 0
