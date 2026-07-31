#!/usr/bin/env python3
"""Verify a compact Synthetic Confirmatory v3 bootstrap-repair artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--allow-formal-runtime", action="store_true")
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository / "src"))
    from phase_a_harness.synthetic_confirmatory_v3_bootstrap_repair_artifact_verifier import (
        verify_bootstrap_repair_prerun_artifact,
    )

    report = verify_bootstrap_repair_prerun_artifact(
        args.artifact,
        require_formal_runtime_absent=not args.allow_formal_runtime,
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["PRE_RUN_ARTIFACT_VERIFICATION_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
