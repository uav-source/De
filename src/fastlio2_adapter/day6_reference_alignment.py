"""Exact-key alignment helpers for Day 6 Fallback comparisons."""

from __future__ import annotations

import csv
import json
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from .day6_fallback_functional_diagnostics import (
    Day6FallbackError,
    EXPECTED_AUTHORIZATION_SHA256,
    EXPECTED_FROZEN_ADAPTER_SHA256,
    EXPECTED_FROZEN_BINARY_SHA256,
    EXPECTED_FROZEN_REFERENCE_SHA256,
    EXPECTED_RECORD_COUNT,
    sha256_file,
)
from .day6_statistical_characterization import (
    aligned_output_differences,
    summarize_aligned_differences,
)


def record_key(row: Mapping[str, Any]) -> tuple[int, float, float]:
    return (
        int(row["scan_index"]),
        float(row["timestamp_begin"]),
        float(row["timestamp_end"]),
    )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise Day6FallbackError("JSONL rows must be objects")
    return rows


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _safe_extract(archive: Path, destination: Path) -> Path:
    with tarfile.open(archive, "r:gz") as handle:
        members = handle.getmembers()
        roots = {
            Path(member.name).parts[0]
            for member in members
            if member.name and Path(member.name).parts
        }
        if len(roots) != 1:
            raise Day6FallbackError("archive must have exactly one root")
        destination_resolved = destination.resolve()
        for member in members:
            if member.issym() or member.islnk():
                raise Day6FallbackError("archive links are forbidden")
            try:
                (destination / member.name).resolve().relative_to(
                    destination_resolved
                )
            except ValueError as error:
                raise Day6FallbackError("unsafe archive member") from error
        handle.extractall(destination)
    return destination / next(iter(roots))


def load_frozen_reference(
    frozen_archive: Path, authorization_archive: Path
) -> tuple[list[dict[str, str]], list[dict[str, Any]], dict[str, Any]]:
    if sha256_file(frozen_archive) != EXPECTED_FROZEN_REFERENCE_SHA256:
        raise Day6FallbackError("frozen reference SHA mismatch")
    with tempfile.TemporaryDirectory(prefix="day6_reference_") as temporary:
        temporary_path = Path(temporary)
        frozen_root = _safe_extract(
            frozen_archive, temporary_path / "frozen"
        )
        binary = frozen_root / "binary/observation_records_v3.bin"
        if sha256_file(binary) != EXPECTED_FROZEN_BINARY_SHA256:
            raise Day6FallbackError("frozen reference binary SHA mismatch")
        index = load_csv(frozen_root / "index/record_index.csv")
        if authorization_archive.suffix == ".jsonl":
            adapter_path = authorization_archive
        else:
            if (
                sha256_file(authorization_archive)
                != EXPECTED_AUTHORIZATION_SHA256
            ):
                raise Day6FallbackError("authorization audit SHA mismatch")
            auth_root = _safe_extract(
                authorization_archive, temporary_path / "authorization"
            )
            adapter_path = (
                auth_root
                / "canonical_output/adapter_detector_outputs_v3.jsonl"
            )
        if sha256_file(adapter_path) != EXPECTED_FROZEN_ADAPTER_SHA256:
            raise Day6FallbackError("frozen adapter output SHA mismatch")
        outputs = load_jsonl(adapter_path)
        manifest = json.loads(
            (frozen_root / "FREEZE_MANIFEST.json").read_text(encoding="utf-8")
        )
    if len(index) != EXPECTED_RECORD_COUNT or len(outputs) != EXPECTED_RECORD_COUNT:
        raise Day6FallbackError("frozen reference count mismatch")
    return index, outputs, manifest


def align_reference_run(
    reference_index: Sequence[Mapping[str, Any]],
    reference_outputs: Sequence[Mapping[str, Any]],
    run_index: Sequence[Mapping[str, Any]],
    run_outputs: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reference_output_map = {record_key(row): row for row in reference_outputs}
    run_output_map = {record_key(row): row for row in run_outputs}
    reference_keys = [record_key(row) for row in reference_index]
    run_keys = [record_key(row) for row in run_index]
    shared = sorted(set(reference_keys) & set(run_keys))
    rows: list[dict[str, Any]] = []
    for key in shared:
        reference = reference_output_map[key]
        run = run_output_map[key]
        rows.append(
            {
                "scan_index": key[0],
                "timestamp_begin": repr(key[1]),
                "timestamp_end": repr(key[2]),
                "timestamp_identity": True,
                **aligned_output_differences(reference, run),
            }
        )
    summary = {
        "schema_version": "day6_reference_alignment_summary_v1",
        "reference_count": len(reference_keys),
        "run_count": len(run_keys),
        "aligned_count": len(shared),
        "reference_only_count": len(set(reference_keys) - set(run_keys)),
        "run_only_count": len(set(run_keys) - set(reference_keys)),
        "timestamp_identity_count": len(shared),
        "REFERENCE_OUTPUT_BITWISE_EQUALITY_REQUIRED": False,
        "REFERENCE_OBSERVATION_BITWISE_EQUALITY_REQUIRED": False,
        **summarize_aligned_differences(rows),
    }
    summary["reference_alignment_pass"] = (
        summary["reference_count"] == EXPECTED_RECORD_COUNT
        and summary["run_count"] == EXPECTED_RECORD_COUNT
        and summary["aligned_count"] == EXPECTED_RECORD_COUNT
        and summary["reference_only_count"] == 0
        and summary["run_only_count"] == 0
    )
    if not summary["reference_alignment_pass"]:
        raise Day6FallbackError(f"reference alignment failed: {summary}")
    return rows, summary
