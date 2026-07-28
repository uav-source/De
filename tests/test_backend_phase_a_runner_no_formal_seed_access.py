import numpy as np

from backend_phase_a_v1_1_test_support import ROOT, write_valid_lock
from zero_perturbation.backend_phase_a_v1_1 import dry_run


def test_dry_run_never_constructs_formal_rng(monkeypatch, tmp_path):
    lock = tmp_path / "lock.json"
    write_valid_lock(lock)

    def forbidden(*args, **kwargs):
        raise AssertionError("RNG construction is forbidden in dry-run")

    monkeypatch.setattr(np.random, "PCG64", forbidden)
    report = dry_run(
        root=ROOT,
        protocol_lock=lock,
        run_id="no-formal-seeds",
        output_dir=tmp_path / "out",
        workers=1,
    )
    assert report["DRY_RUN_RNG_INSTANTIATION_COUNT"] == 0

