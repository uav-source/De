import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs/capture_range/day2_synthetic_locked.yaml"
PROTOCOL_DOC = ROOT / "docs/directional_capture_range_day2_protocol.md"
PROTOCOL_ORIGIN = "prospectively_frozen_after_day1_and_before_any_day2_run"
DAY1_COMMIT = "91f2d07f0b112a339702ea72f4055404cd356fdf"
DAY1_TAG = "archive/directional-capture-range-day1-pass"


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True
    ).strip()


def test_protocol_origin_is_explicitly_recorded_and_supported_by_the_lock():
    # This exact value is protocol-lock evidence required by the Day 2 execution order.
    assert PROTOCOL_ORIGIN == (
        "prospectively_frozen_after_day1_and_before_any_day2_run"
    )
    with PROTOCOL_PATH.open("r", encoding="utf-8") as stream:
        protocol = yaml.safe_load(stream)
    documentation = PROTOCOL_DOC.read_text(encoding="utf-8")

    assert protocol["protocol"]["status"] == (
        "prospectively_frozen_before_any_day2_run"
    )
    assert protocol["protocol"]["day1_required_commit"] == DAY1_COMMIT
    assert protocol["protocol"]["day1_required_tag"] == DAY1_TAG
    assert "prospectively frozen **before any Day 2 development or test run**" in documentation
    assert f"commit: `{DAY1_COMMIT}`" in documentation
    assert f"tag: `{DAY1_TAG}`" in documentation


def test_required_day1_baseline_precedes_the_day2_protocol_lock_work():
    assert _git("rev-parse", f"{DAY1_TAG}^{{commit}}") == DAY1_COMMIT
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", DAY1_COMMIT, "HEAD"],
        cwd=ROOT,
        check=True,
    )

    for relative_path in (
        "configs/capture_range/day2_synthetic_locked.yaml",
        "docs/directional_capture_range_day2_protocol.md",
    ):
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{DAY1_COMMIT}:{relative_path}"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode != 0
