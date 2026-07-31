#!/usr/bin/env python3
"""Verify a compact Synthetic Confirmatory v3 bootstrap-repair r2 artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args(argv)

    repository = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository / "src"))
    from phase_a_harness.synthetic_confirmatory_v3_bootstrap_repair_r2_artifact_verifier import (
        BootstrapRepairR2ArtifactError,
        verify_bootstrap_repair_r2_prerun_artifact,
    )

    try:
        report = verify_bootstrap_repair_r2_prerun_artifact(args.artifact)
    except BootstrapRepairR2ArtifactError as error:
        report = {
            "PRE_RUN_ARTIFACT_VERIFICATION_PASS": False,
            "error": str(error),
            "schema_version": (
                "synthetic_confirmatory_v3_bootstrap_repair_r2_"
                "artifact_verification_v1"
            ),
        }
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["PRE_RUN_ARTIFACT_VERIFICATION_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
