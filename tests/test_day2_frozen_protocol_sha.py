import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DAY1_COMMIT = "91f2d07f0b112a339702ea72f4055404cd356fdf"
DAY1_TAG = "archive/directional-capture-range-day1-pass"

FROZEN_FILE_SHA256 = {
    "configs/capture_range/day2_synthetic_locked.yaml": (
        "3b2f007c1d68d2399493ce5e15775120c4936495e4c08ef3fd0df1a88c35db65"
    ),
    "docs/directional_capture_range_day2_protocol.md": (
        "765f3eb755db18559fa0a83a1729512f2123b9ce658169542491faecc59e7bd4"
    ),
}

DAY1_ARTIFACT_SHA256 = {
    "SHA256SUMS": "901c18515b4d263f4cee795a647c19dc6eff34899647d5cecc7a00da69086117",
    "capture_radius_summary.csv": (
        "b8c0236b7c77cd3a3250a71ac9e7b43077667029eddd12349abbc8a4a6bc0337"
    ),
    "direction_curves.csv": (
        "be746caa0ede2c6f88252c0ad53e60de16ef51bdabaf601a4c7fabd0caf43b62"
    ),
    "protocol_lock.json": (
        "2fef48fd9682c3cab64279f3780a0a13655fc6243012c4ef4e22187ccc8d8eca"
    ),
    "run_manifest.json": (
        "0c89b009255479f3c66231dd6c667578dd4c5f0d917c8032c63aa45bf3e8079e"
    ),
    "runtime_summary.csv": (
        "af158c8e69c28248fd5ab382278de37772097706efd7239d06c93d05dd436a42"
    ),
    "smoke_report.md": (
        "ae96363f4869e19aabf310ced376b8552215e204eb6d69c54b9b891a1945b3a6"
    ),
    "trial_results.csv": (
        "9463472bb1d2026a76cf62e18daecf166bb5001692162240a68d12676945664a"
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True
    ).strip()


def test_supplied_day2_protocol_files_are_byte_exact():
    for relative_path, expected_sha256 in FROZEN_FILE_SHA256.items():
        assert _sha256(ROOT / relative_path) == expected_sha256


def test_day1_tag_still_resolves_to_the_required_commit():
    assert _git("rev-parse", f"{DAY1_TAG}^{{commit}}") == DAY1_COMMIT


def test_day1_artifacts_remain_byte_exact():
    artifact_root = ROOT / "artifacts/current/directional_capture_range_day1"
    assert {path.name for path in artifact_root.iterdir() if path.is_file()} == set(
        DAY1_ARTIFACT_SHA256
    )
    for filename, expected_sha256 in DAY1_ARTIFACT_SHA256.items():
        assert _sha256(artifact_root / filename) == expected_sha256
