"""Deterministic FAST-LIO2 runtime-output source scan and allowlist audit."""

from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from .source_lock import RUNTIME_OUTPUT_DEFINITIONS


SCAN_SCHEMA_VERSION = "FASTLIO2_RUNTIME_OUTPUT_SOURCE_SCAN_V1"
RUNTIME_PRODUCT_PATHS = {
    "runtime_audit_v2.bin": (
        "src/runtime_equivalence_audit.cpp",
        120,
        "writer_.configure",
        "binary",
        "AUDIT_ONLY, CAPTURE_ONLY, or COMPACT_EXPORT",
    ),
    "final_map_summary.json": (
        "src/runtime_equivalence_audit.cpp",
        395,
        "RuntimeEquivalenceAudit::writeFinalMapSummary",
        "std::ios::out | std::ios::trunc",
        "runtime equivalence audit enabled",
    ),
    "run_summary.json": (
        "src/runtime_equivalence_audit.cpp",
        426,
        "RuntimeEquivalenceAudit::writeSummary",
        "std::ios::out | std::ios::trunc",
        "runtime equivalence audit enabled",
    ),
    "tap_export_summary.json": (
        "src/laserMapping.cpp",
        1655,
        "tap_summary",
        "ios::out | ios::trunc",
        "runtime equivalence audit enabled",
    ),
    "observation_records_v3.bin": (
        "src/laserMapping.cpp",
        1326,
        "observation_writer_config.path",
        "binary",
        "CAPTURE_ONLY or COMPACT_EXPORT only",
    ),
}

FIELDS = (
    "source_file",
    "line_number",
    "symbol",
    "expression",
    "resolved_relative_path",
    "output_root",
    "open_mode",
    "allowlisted",
    "allowlist_reason",
    "confidence",
    "notes",
)


def _source_line(root: Path, relative: str, line_number: int) -> str:
    lines = (root / relative).read_text(encoding="utf-8", errors="replace").splitlines()
    if line_number < 1 or line_number > len(lines):
        return ""
    return lines[line_number - 1].strip()


def _row(
    root: Path,
    *,
    source_file: str,
    line_number: int,
    symbol: str,
    resolved_relative_path: str,
    output_root: str,
    open_mode: str,
    reason: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "source_file": source_file,
        "line_number": line_number,
        "symbol": symbol,
        "expression": _source_line(root, source_file, line_number),
        "resolved_relative_path": resolved_relative_path,
        "output_root": output_root,
        "open_mode": open_mode,
        "allowlisted": True,
        "allowlist_reason": reason,
        "confidence": "CONFIRMED",
        "notes": notes,
    }


def scan_runtime_outputs(root: Path) -> list[dict[str, Any]]:
    """Scan the frozen production tree and resolve every supported output."""
    root = root.resolve()
    rows: list[dict[str, Any]] = []
    for definition in RUNTIME_OUTPUT_DEFINITIONS:
        rows.append(
            _row(
                root,
                source_file=str(definition["source_file"]),
                line_number=int(definition["source_line"]),
                symbol=str(definition["source_symbol"]),
                resolved_relative_path=str(definition["path"]),
                output_root=str(definition["path"]).split("/", 1)[0],
                open_mode=str(definition["open_mode"]),
                reason=str(definition["reason"]),
                notes=str(definition["enabled_condition"]),
            )
        )
    for relative, (source_file, line_number, symbol, mode, condition) in sorted(
        RUNTIME_PRODUCT_PATHS.items(), key=lambda item: os.fsencode(item[0])
    ):
        rows.append(
            _row(
                root,
                source_file=source_file,
                line_number=line_number,
                symbol=symbol,
                resolved_relative_path=relative,
                output_root="RUNTIME_EQUIVALENCE_OUTPUT_DIR",
                open_mode=mode,
                reason="required or mode-gated per-run runtime product",
                notes=condition,
            )
        )

    # Fail closed if a frozen DEBUG_FILE_DIR output is not represented.
    discovered_debug: set[tuple[str, int, str]] = set()
    for path in sorted((root / "src").rglob("*"), key=lambda value: os.fsencode(str(value))):
        if not path.is_file() or path.suffix not in {".cpp", ".hpp", ".h", ".cc"}:
            continue
        for number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for match in re.finditer(r'DEBUG_FILE_DIR\("([^"]+)"\)', line):
                discovered_debug.add(
                    (path.relative_to(root).as_posix(), number, f"Log/{match.group(1)}")
                )
    represented = {
        (str(row["source_file"]), int(row["line_number"]), str(row["resolved_relative_path"]))
        for row in rows
    }
    for source_file, number, relative in sorted(discovered_debug):
        if (source_file, number, relative) not in represented:
            rows.append(
                {
                    "source_file": source_file,
                    "line_number": number,
                    "symbol": "DEBUG_FILE_DIR",
                    "expression": _source_line(root, source_file, number),
                    "resolved_relative_path": relative,
                    "output_root": "Log",
                    "open_mode": "UNRESOLVED",
                    "allowlisted": False,
                    "allowlist_reason": "",
                    "confidence": "UNRESOLVED",
                    "notes": "DEBUG_FILE_DIR output missing from frozen allowlist",
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            os.fsencode(str(row["source_file"])),
            int(row["line_number"]),
            os.fsencode(str(row["resolved_relative_path"])),
        ),
    )


def scan_summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    values = list(rows)
    unresolved = [row for row in values if row["confidence"] == "UNRESOLVED"]
    confirmed_unallowlisted = [
        row
        for row in values
        if row["confidence"] == "CONFIRMED" and not bool(row["allowlisted"])
    ]
    return {
        "schema_version": SCAN_SCHEMA_VERSION,
        "runtime_output_source_count": len(values),
        "runtime_output_unresolved_count": len(unresolved),
        "confirmed_unallowlisted_count": len(confirmed_unallowlisted),
        "runtime_output_contract_pass": not unresolved and not confirmed_unallowlisted,
    }


def write_source_scan_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            encoded["allowlisted"] = "true" if row["allowlisted"] else "false"
            writer.writerow(encoded)
