from backend_phase_a_v1_1_test_support import ROOT, write_valid_lock
from zero_perturbation.backend_phase_a_v1_1 import dry_run


def test_runner_dry_run_reports_210_420_without_execution(tmp_path):
    lock = tmp_path / "lock.json"
    write_valid_lock(lock)
    report = dry_run(
        root=ROOT,
        protocol_lock=lock,
        run_id="v1-1-contract-dry-run",
        output_dir=tmp_path / "formal-output-never-created",
        workers=4,
    )
    assert report["DRY_RUN_PLANNED_SNAPSHOT_COUNT"] == 210
    assert report["DRY_RUN_PLANNED_TRIAL_COUNT"] == 420
    assert report["DRY_RUN_RNG_INSTANTIATION_COUNT"] == 0
    assert report["DRY_RUN_SNAPSHOT_GENERATION_COUNT"] == 0
    assert report["DRY_RUN_BACKEND_EXECUTION_COUNT"] == 0
    assert report["DRY_RUN_TRIAL_RESULT_COUNT"] == 0
    assert not (tmp_path / "formal-output-never-created").exists()

