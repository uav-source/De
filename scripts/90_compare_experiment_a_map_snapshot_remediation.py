#!/usr/bin/env python3
"""Compare the two coherent-map Experiment A replay windows offline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.experiment_a_stage_classifier import (  # noqa: E402
    compare_pair,
    load_records,
    write_comparison,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-1", required=True, type=Path)
    parser.add_argument("--run-2", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = compare_pair(load_records(args.run_1), load_records(args.run_2))
    write_comparison(result, args.output_dir)
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "rows"},
            sort_keys=True,
        )
    )
    return 0 if result["comparison_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
