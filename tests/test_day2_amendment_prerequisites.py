import subprocess
from pathlib import Path

from capture_range.day2_protocol import (
    AMENDMENT_LOCK_TAG,
    AMENDMENT_MARKDOWN_RELATIVE,
    AMENDMENT_YAML_RELATIVE,
    BASE_LOCK_COMMIT,
    BASE_LOCK_TAG,
    load_effective_day2_protocol,
)


ROOT = Path(__file__).resolve().parents[1]
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


def _amendment_tag_exists() -> bool:
    return _git(
        "rev-parse", "--verify", "--quiet", f"refs/tags/{AMENDMENT_LOCK_TAG}",
        check=False,
    ).returncode == 0


def _pre_amendment_tree() -> str:
    if _amendment_tag_exists():
        lock = _git("rev-parse", f"{AMENDMENT_LOCK_TAG}^{{commit}}").stdout.strip()
        return _git("rev-parse", f"{lock}^").stdout.strip()
    return BASE_LOCK_COMMIT


def test_v1_1_base_commit_tag_and_historical_timing_match():
    effective = load_effective_day2_protocol(ROOT)
    metadata = effective.amendment["amendment"]

    assert _git("rev-parse", f"{BASE_LOCK_TAG}^{{commit}}").stdout.strip() == (
        BASE_LOCK_COMMIT
    )
    assert metadata["base_protocol"]["lock_commit"] == BASE_LOCK_COMMIT
    assert metadata["base_protocol"]["lock_tag"] == BASE_LOCK_TAG
    for relative_path in (AMENDMENT_YAML_RELATIVE, AMENDMENT_MARKDOWN_RELATIVE):
        assert _git(
            "cat-file", "-e", f"{BASE_LOCK_COMMIT}:{relative_path}", check=False
        ).returncode != 0


def test_no_result_or_seed_was_consumed_before_amendment():
    effective = load_effective_day2_protocol(ROOT)
    prerequisites = effective.amendment["amendment"]["prerequisites"]

    assert prerequisites == {
        "day2_results_existed_before_amendment": False,
        "day2_test_seeds_consumed_before_amendment": False,
        "development_runs_completed_before_amendment": 0,
        "test_runs_completed_before_amendment": 0,
    }
    assert _git(
        "ls-tree", "-r", "--name-only", _pre_amendment_tree(), "--",
        *DAY2_RESULT_ROOTS,
    ).stdout == ""
    if not _amendment_tag_exists():
        assert [
            path
            for root in DAY2_RESULT_ROOTS
            for path in (ROOT / root).rglob("*")
            if path.is_file()
        ] == []


def test_reserved_test_seeds_remain_disjoint_and_unconsumed():
    effective = load_effective_day2_protocol(ROOT)
    development = effective.base["splits"]["development"]
    reserved = effective.base["splits"]["test"]

    assert reserved["geometry_seeds"] == (1201, 1213, 1223)
    assert reserved["measurement_seeds"] == (2203, 2213)
    assert set(development["geometry_seeds"]).isdisjoint(reserved["geometry_seeds"])
    assert set(development["measurement_seeds"]).isdisjoint(
        reserved["measurement_seeds"]
    )
