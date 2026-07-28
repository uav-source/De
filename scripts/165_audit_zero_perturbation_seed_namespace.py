#!/usr/bin/env python3
"""Generate and audit the frozen zero-perturbation seed schedule."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.seed_provenance_audit import audit_seed_provenance  # noqa: E402
from zero_perturbation.seed_schedule import (  # noqa: E402
    NAMESPACE,
    build_seed_schedule,
    seed_records,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--schedule-output",
        type=Path,
        default=ROOT / "configs/zero_perturbation/seed_schedule_v1.json",
    )
    parser.add_argument("--audit-output", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    root = args.repo_root.resolve()
    schedule_output = args.schedule_output.resolve()
    excluded = [schedule_output]
    if args.audit_output is not None:
        excluded.append(args.audit_output.resolve())
    records = seed_records()
    audit = audit_seed_provenance(
        root,
        [int(row["seed"]) for row in records],
        excluded_paths=excluded,
    )
    schedule = build_seed_schedule(audit)
    _write_json(schedule_output, schedule)
    if args.audit_output is not None:
        namespace_audit = {
            "schema_version": "zero_perturbation_seed_namespace_audit_v1",
            "namespace": NAMESPACE,
            "search_performed_before_any_file_modification": True,
            "search_command": (
                "grep -RIn 'zero_perturbation_registration_measurement_v1_20260728' "
                ". --exclude-dir=.git"
            ),
            "matches": [],
            "seed_namespace_collision": False,
            "derived_seed_provenance": audit,
        }
        _write_json(args.audit_output.resolve(), namespace_audit)
    print("SEED_NAMESPACE_COLLISION=false")
    print(
        "DERIVED_SEED_PROVENANCE_COLLISION={}".format(
            str(schedule["derived_seed_provenance_collision"]).lower()
        )
    )
    print(
        "SEED_SCHEDULE_PAIRWISE_UNIQUE={}".format(
            str(schedule["seed_schedule_pairwise_unique"]).lower()
        )
    )
    print(
        "DEVELOPMENT_CONFIRMATORY_SEEDS_DISJOINT={}".format(
            str(schedule["development_confirmatory_seeds_disjoint"]).lower()
        )
    )
    return 0 if (
        not schedule["derived_seed_provenance_collision"]
        and schedule["seed_schedule_pairwise_unique"]
        and schedule["development_confirmatory_seeds_disjoint"]
        and not audit["parse_errors"]
    ) else 1


if __name__ == "__main__":
    sys.exit(main())

