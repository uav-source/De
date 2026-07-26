from __future__ import annotations

import csv
from pathlib import Path

from fastlio2_adapter.runtime_output_contract import (
    scan_runtime_outputs,
    scan_summary,
    write_source_scan_csv,
)
from fastlio2_adapter.source_lock import RUNTIME_OUTPUT_PATHS


FAST_ROOT = Path.home() / "fastlio2_ws/src/FAST_LIO"


def test_complete_frozen_output_contract_and_imu_source():
    rows = scan_runtime_outputs(FAST_ROOT)
    summary = scan_summary(rows)
    assert summary["runtime_output_contract_pass"] is True
    assert summary["runtime_output_unresolved_count"] == 0
    assert summary["confirmed_unallowlisted_count"] == 0
    paths = {row["resolved_relative_path"] for row in rows}
    assert set(RUNTIME_OUTPUT_PATHS) <= paths
    imu = next(row for row in rows if row["resolved_relative_path"] == "Log/imu.txt")
    assert imu["source_file"] == "src/IMU_Processing.hpp"
    assert imu["line_number"] == 376
    assert 'DEBUG_FILE_DIR("imu.txt")' in imu["expression"]


def test_all_debug_file_macros_are_discovered():
    rows = scan_runtime_outputs(FAST_ROOT)
    expressions = "\n".join(str(row["expression"]) for row in rows)
    source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted((FAST_ROOT / "src").rglob("*"))
        if path.is_file() and path.suffix in {".cpp", ".hpp", ".h", ".cc"}
    )
    assert source.count("DEBUG_FILE_DIR(") == expressions.count("DEBUG_FILE_DIR(")


def test_source_scan_csv_is_byte_deterministic(tmp_path):
    rows = scan_runtime_outputs(FAST_ROOT)
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    write_source_scan_csv(first, rows)
    write_source_scan_csv(second, scan_runtime_outputs(FAST_ROOT))
    assert first.read_bytes() == second.read_bytes()
    with first.open(encoding="utf-8", newline="") as stream:
        parsed = list(csv.DictReader(stream))
    assert parsed
    assert {row["confidence"] for row in parsed} == {"CONFIRMED"}


def test_runtime_outputs_are_not_source_lock_inputs():
    assert all(path.startswith(("Log/", "PCD/")) for path in RUNTIME_OUTPUT_PATHS)
