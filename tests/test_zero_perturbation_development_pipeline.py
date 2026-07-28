from zero_perturbation.pipeline import enumerate_snapshot_keys
from zero_perturbation_test_support import development_protocol


def test_development_pipeline_enumerates_1260_and_smoke_42_snapshots():
    protocol = development_protocol()
    full = enumerate_snapshot_keys(protocol)
    smoke = enumerate_snapshot_keys(protocol, smoke=True)
    assert len(full) == 1260
    assert len({key.snapshot_id for key in full}) == 1260
    assert len(smoke) == 42
