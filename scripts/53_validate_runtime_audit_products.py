#!/usr/bin/env python3
"""Validate stable Day 5 runtime products and the compact binary trailer."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PRODUCTS = (
    "runtime_audit_v2.bin",
    "run_summary.json",
    "final_map_summary.json",
    "tap_export_summary.json",
)


class RuntimeProductError(RuntimeError):
    def __init__(self, classification: str, message: str) -> None:
        super().__init__(message)
        self.classification = classification


def _load_converter() -> Any:
    path = ROOT / "scripts/46_convert_fastlio2_runtime_binary.py"
    spec = importlib.util.spec_from_file_location("day5_binary_converter_v3", path)
    if spec is None or spec.loader is None:
        raise RuntimeProductError("RUNTIME_BINARY_CHECKSUM_FAILURE", "cannot load binary converter")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _snapshot(paths: Iterable[Path]) -> tuple[tuple[str, int, int], ...]:
    rows = []
    for path in paths:
        if not path.is_file():
            raise RuntimeProductError("RUNTIME_PRODUCT_MISSING", f"required runtime product missing: {path.name}")
        details = path.stat()
        rows.append((path.name, details.st_size, details.st_mtime_ns))
    return tuple(rows)


def wait_for_stable_products(
    paths: Iterable[Path],
    *,
    poll_interval: float = 0.2,
    stable_polls: int = 5,
    timeout: float = 5.0,
) -> dict[str, Any]:
    values = tuple(paths)
    deadline = time.monotonic() + timeout
    previous: tuple[tuple[str, int, int], ...] | None = None
    observed = 0
    poll_count = 0
    while time.monotonic() <= deadline:
        current = _snapshot(values)
        poll_count += 1
        if current == previous:
            observed += 1
        else:
            previous = current
            observed = 1
        if observed >= stable_polls:
            return {
                "stable": True,
                "stable_poll_required": stable_polls,
                "stable_poll_observed": observed,
                "poll_count": poll_count,
                "files": [
                    {"path": name, "size_bytes": size, "mtime_ns": mtime}
                    for name, size, mtime in current
                ],
            }
        time.sleep(poll_interval)
    raise RuntimeProductError("RUNTIME_PRODUCT_MISSING", "runtime products did not become stable")


def normalize_tap_export_summary(path: Path) -> dict[str, Any]:
    """Add explicit V3 contract aliases without changing FAST-LIO2 source."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeProductError("RUNTIME_PRODUCT_MISSING", f"invalid tap export summary: {error}") from error
    mode = value.get("mode", value.get("runtime_mode"))
    count = value.get(
        "observation_record_count",
        value.get("binary_observation_record_count"),
    )
    value["mode"] = mode
    value["observation_record_count"] = count
    temporary = path.with_name(path.name + ".v3-normalized")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return value


def _binary_classification(message: str) -> str:
    lowered = message.lower()
    if "extra" in lowered or "truncated record length" in lowered:
        return "RUNTIME_BINARY_EXTRA_BYTES"
    if "record count" in lowered:
        return "RUNTIME_BINARY_RECORD_COUNT_MISMATCH"
    if "checksum" in lowered:
        return "RUNTIME_BINARY_CHECKSUM_FAILURE"
    if "trailer" in lowered:
        return "RUNTIME_BINARY_TRAILER_MISSING"
    if "truncated" in lowered:
        return "RUNTIME_BINARY_TRUNCATED"
    return "RUNTIME_BINARY_CHECKSUM_FAILURE"


def validate_runtime_products(run_dir: Path, converted_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve(strict=False)
    paths = [run_dir / name for name in REQUIRED_PRODUCTS]
    if (run_dir / "tap_export_summary.json").is_file():
        normalize_tap_export_summary(run_dir / "tap_export_summary.json")
    stability = wait_for_stable_products(paths)
    binary_path, run_summary_path, final_map_path, tap_path = paths
    converter = _load_converter()
    try:
        records, binary = converter.read_framed_binary(
            binary_path,
            magic=converter.RUNTIME_MAGIC,
            version=converter.RUNTIME_VERSION,
        )
        decoded = [converter.decode_runtime_record(record) for record in records]
    except converter.BinaryFormatError as error:
        raise RuntimeProductError(_binary_classification(str(error)), str(error)) from error
    if converted_dir.exists():
        raise RuntimeProductError("RUNTIME_PRODUCT_MISSING", f"converter output already exists: {converted_dir}")
    try:
        conversion = converter.convert_files(binary_path, converted_dir)
    except converter.BinaryFormatError as error:
        raise RuntimeProductError(_binary_classification(str(error)), str(error)) from error

    try:
        run_summary = json.loads(run_summary_path.read_text(encoding="utf-8"))
        final_map = json.loads(final_map_path.read_text(encoding="utf-8"))
        tap = json.loads(tap_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeProductError("RUNTIME_PRODUCT_MISSING", f"invalid runtime JSON: {error}") from error
    summary_count = run_summary.get(
        "runtime_record_count",
        run_summary.get("runtime_audit_record_count"),
    )
    if summary_count != binary["record_count"] or len(decoded) != binary["record_count"]:
        raise RuntimeProductError(
            "RUNTIME_BINARY_RECORD_COUNT_MISMATCH",
            "run summary, decoded rows, and binary trailer record count disagree",
        )
    if int(final_map.get("final_map_point_count", -1)) < 0:
        raise RuntimeProductError("RUNTIME_PRODUCT_MISSING", "invalid final map point count")
    if final_map.get("final_map_checksum") in (None, ""):
        raise RuntimeProductError("RUNTIME_PRODUCT_MISSING", "empty final map checksum")
    if tap.get("mode", tap.get("runtime_mode")) != "AUDIT_ONLY":
        raise RuntimeProductError("RUNTIME_PRODUCT_MISSING", "tap summary mode is not AUDIT_ONLY")
    if tap.get("tap_enabled") is not False:
        raise RuntimeProductError("RUNTIME_PRODUCT_MISSING", "tap summary reports tap enabled")
    observation_count = tap.get(
        "observation_record_count",
        tap.get("binary_observation_record_count"),
    )
    if observation_count != 0:
        raise RuntimeProductError("RUNTIME_PRODUCT_MISSING", "AUDIT_ONLY observation count is nonzero")
    return {
        "runtime_product_pass": True,
        "required_runtime_product_names": list(REQUIRED_PRODUCTS),
        "required_runtime_product_count": len(REQUIRED_PRODUCTS),
        "runtime_product_missing_count": 0,
        "runtime_binary_path": binary_path.name,
        "runtime_binary_size_bytes": binary_path.stat().st_size,
        "runtime_binary_trailer_pass": True,
        "runtime_binary_checksum_pass": True,
        "runtime_binary_record_count": binary["record_count"],
        "runtime_frame_row_count": conversion["runtime_record_count"],
        "binary_checksum_failure_count": 0,
        "run_summary_pass": True,
        "final_map_summary_pass": True,
        "tap_export_summary_pass": True,
        "tap_enabled": False,
        "observation_record_count": 0,
        "stability": stability,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--converted-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate_runtime_products(args.run_dir, args.converted_dir)
    except RuntimeProductError as error:
        result = {
            "runtime_product_pass": False,
            "failure_classification": error.classification,
            "message": str(error),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
