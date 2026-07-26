#!/usr/bin/env python3
"""Recompute all six full-stream and focused-stage comparisons."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day6_semantic_observation import load_observation_records
from fastlio2_adapter.focused_branch_stage_classifier import (
    load_focused_records,
)
from fastlio2_adapter.focused_branch_stage_localization import (
    compare_all,
    write_comparison,
)
from fastlio2_adapter.formal_trajectory_clustering import (
    cluster_formal_trajectories,
    write_clusters,
)

RUN_IDS = tuple(
    f"multihyp_day6_focused_branch_r{index}" for index in range(1, 5)
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    observations = {}
    stage = {}
    integrity = {}
    for run_id in RUN_IDS:
        run = args.runtime_root / run_id
        observations[run_id], integrity[run_id] = load_observation_records(
            run / "observation_records_v3.bin"
        )
        stage[run_id] = load_focused_records(
            run / "experiment_a_stage_hash_records_v2.json"
        )
    result = compare_all(
        run_ids=RUN_IDS,
        observations=observations,
        focused_records=stage,
    )
    write_comparison(result, args.output_dir)
    clusters = cluster_formal_trajectories(observations)
    write_clusters(clusters, args.output_dir)
    (args.output_dir / "formal_trajectory_clusters.json").replace(
        args.output_dir / "focused_formal_trajectory_clusters.json"
    )
    (args.output_dir / "formal_trajectory_cluster_membership.csv").replace(
        args.output_dir
        / "focused_formal_trajectory_cluster_membership.csv"
    )
    (args.output_dir / "observation_integrity_summary.json").write_text(
        json.dumps(integrity, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

