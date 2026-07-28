#!/usr/bin/env python3
"""Guarded future Phase A execution entry; never invoked by the lock round."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_phase_a_protocol import (
    validate_protocol_lock_document,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the locked dual-backend Phase A matrix"
    )
    parser.add_argument("--protocol-lock", type=Path, required=True)
    parser.add_argument("--pcl-cli", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def execution_entry(
    protocol_lock: Path, pcl_cli: Path, output_root: Path
) -> None:
    """Validate authority first; formal execution is implemented in the run round."""

    validate_protocol_lock_document(protocol_lock, ROOT)
    if not pcl_cli.is_file():
        raise FileNotFoundError("frozen PCL CLI does not exist")
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError("Phase A output root must be absent or empty")
    raise RuntimeError(
        "Phase A execution body is intentionally deferred to the authorized run round"
    )


def main() -> int:
    args = build_parser().parse_args()
    execution_entry(args.protocol_lock, args.pcl_cli, args.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
