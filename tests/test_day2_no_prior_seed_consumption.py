import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs/capture_range/day2_synthetic_locked.yaml"
DAY1_COMMIT = "91f2d07f0b112a339702ea72f4055404cd356fdf"
PROTOCOL_LOCK_TAG = "archive/directional-capture-range-day2-protocol-lock"
DAY2_RESULTS_EXISTED_BEFORE_PROTOCOL_LOCK = False
DAY2_TEST_SEEDS_CONSUMED_BEFORE_PROTOCOL_LOCK = False
DAY2_RESULT_ROOTS = (
    "results/capture_range/day2",
    "data/capture_range/day2",
    "artifacts/current/directional_capture_range_day2",
)


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def _protocol_lock_exists() -> bool:
    return _git(
        "rev-parse", "--verify", "--quiet", f"refs/tags/{PROTOCOL_LOCK_TAG}",
        check=False,
    ).returncode == 0


def _pre_lock_tree() -> str:
    if _protocol_lock_exists():
        tagged_commit = _git("rev-parse", f"{PROTOCOL_LOCK_TAG}^{{commit}}").stdout.strip()
        return _git("rev-parse", f"{tagged_commit}^").stdout.strip()
    return DAY1_COMMIT


def test_no_day2_result_tree_existed_before_the_protocol_lock():
    assert DAY2_RESULTS_EXISTED_BEFORE_PROTOCOL_LOCK is False
    paths = _git(
        "ls-tree", "-r", "--name-only", _pre_lock_tree(), "--", *DAY2_RESULT_ROOTS
    ).stdout.splitlines()
    assert paths == []

    # Before the archival tag exists, also prove that no ignored/untracked result file
    # is present in the live workspace. After locking, the immutable parent tree above
    # remains the historical proof while later authorized runs may populate these roots.
    if not _protocol_lock_exists():
        present_files = [
            str(path.relative_to(ROOT))
            for root in DAY2_RESULT_ROOTS
            for path in (ROOT / root).rglob("*")
            if path.is_file()
        ]
        assert present_files == []


def test_reserved_test_seeds_were_not_consumed_before_the_protocol_lock():
    assert DAY2_TEST_SEEDS_CONSUMED_BEFORE_PROTOCOL_LOCK is False
    with PROTOCOL_PATH.open("r", encoding="utf-8") as stream:
        protocol = yaml.safe_load(stream)

    development = protocol["splits"]["development"]
    test = protocol["splits"]["test"]
    assert test["geometry_seeds"] == [1201, 1213, 1223]
    assert test["measurement_seeds"] == [2203, 2213]
    assert set(development["geometry_seeds"]).isdisjoint(test["geometry_seeds"])
    assert set(development["measurement_seeds"]).isdisjoint(test["measurement_seeds"])
    assert _git(
        "ls-tree", "-r", "--name-only", _pre_lock_tree(), "--", *DAY2_RESULT_ROOTS
    ).stdout == ""
