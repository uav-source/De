import csv
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from capture_range.pipeline import REQUIRED_OUTPUT_FILES, run_capture_range_smoke
from capture_range.verification import verify_capture_range_day1


ROOT = Path(__file__).resolve().parents[1]
PROTECTED_ARTIFACT_PATHS = (
    "artifacts/current/measurement_real_validation_pilot",
    "artifacts/current/measurement_pilot_scientific_audit",
    "artifacts/history",
)


def _refresh_checksum(directory: Path, name: str) -> None:
    digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
    checksum_path = directory / "SHA256SUMS"
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    checksum_path.write_text(
        "\n".join(
            f"{digest}  {name}" if line.endswith(f"  {name}") else line
            for line in lines
        )
        + "\n",
        encoding="utf-8",
    )


def test_capture_range_day1_smoke_pipeline_is_complete_and_verifiable(tmp_path):
    result = run_capture_range_smoke(
        ROOT / "configs/capture_range/day1_protocol.yaml",
        "capture_range_day1_test",
        repository_root=ROOT,
        output_root=tmp_path / "results",
        artifact_dir=tmp_path / "artifact",
    )
    result_dir = Path(result["result_dir"])
    artifact_dir = Path(result["artifact_dir"])
    assert {path.name for path in result_dir.iterdir()} == set(REQUIRED_OUTPUT_FILES)
    assert {path.name for path in artifact_dir.iterdir()} == set(REQUIRED_OUTPUT_FILES)
    for name in (
        "trial_results.csv",
        "direction_curves.csv",
        "capture_radius_summary.csv",
        "runtime_summary.csv",
    ):
        assert b"\r\n" not in (result_dir / name).read_bytes()

    manifest = result["manifest"]
    assert manifest["trial_counts"] == {
        "total": 1080,
        "full_reassociation": 540,
        "frozen_jacobian": 540,
    }
    assert manifest["gates"]["ENGINEERING_PASS"] is True
    assert manifest["gates"]["FULL_REASSOCIATION_VERIFIED"] is True
    assert manifest["gates"]["FROZEN_JACOBIAN_BASELINE_ISOLATED"] is True
    assert manifest["gates"]["NO_GT_LEAKAGE"] is True
    assert manifest["gates"]["SEED_DETERMINISM_PASS"] is True
    assert manifest["gates"]["SMOKE_PIPELINE_PASS"] is True
    assert manifest["instrumentation"]["optimizer_gt_access_count"] == 0
    assert manifest["randomness"]["deterministic_output_mismatch_count"] == 0

    with (result_dir / "trial_results.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1080
    assert sum(row["measurement_role"] == "formal" for row in rows) == 540
    assert sum(row["measurement_role"] == "baseline_only" for row in rows) == 540

    verified = verify_capture_range_day1(
        artifact_dir,
        require_gate_pass=False,
    )
    assert verified["verified"] is True
    assert verified["trial_count"] == 1080

    pose_tampered = tmp_path / "pose_tampered"
    shutil.copytree(artifact_dir, pose_tampered)
    trial_path = pose_tampered / "trial_results.csv"
    with trial_path.open(newline="", encoding="utf-8") as handle:
        tampered_rows = list(csv.DictReader(handle))
        fieldnames = list(tampered_rows[0])
    far_pose = json.loads(tampered_rows[0]["final_pose"])
    far_pose[1] += 10.0
    tampered_rows[0]["final_pose"] = json.dumps(far_pose, separators=(",", ":"))
    with trial_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tampered_rows)
    _refresh_checksum(pose_tampered, "trial_results.csv")
    with pytest.raises(ValueError, match="translation_error_m"):
        verify_capture_range_day1(pose_tampered, require_gate_pass=False)

    gate_tampered = tmp_path / "gate_tampered"
    shutil.copytree(artifact_dir, gate_tampered)
    manifest_path = gate_tampered / "run_manifest.json"
    tampered_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tampered_manifest["gates"]["ENGINEERING_PASS"] = False
    tampered_manifest["DAY1_ENGINEERING_GATE"] = "FAIL"
    tampered_manifest["DAY2_AUTHORIZED"] = False
    manifest_path.write_text(
        json.dumps(tampered_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_checksum(gate_tampered, "run_manifest.json")
    with pytest.raises(ValueError, match="stored Day 1 gates"):
        verify_capture_range_day1(gate_tampered, require_gate_pass=False)


@pytest.mark.parametrize("protected_relative", PROTECTED_ARTIFACT_PATHS)
def test_capture_range_pipeline_rejects_protected_artifact_trees(
    tmp_path, protected_relative
):
    with pytest.raises(ValueError, match="protected artifact tree"):
        run_capture_range_smoke(
            ROOT / "configs/capture_range/day1_protocol.yaml",
            "must_not_run",
            repository_root=ROOT,
            output_root=tmp_path / "results",
            artifact_dir=ROOT / protected_relative / "capture_range_forbidden",
        )
