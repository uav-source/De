#!/usr/bin/env python3
"""Compare four fixed bounded branch reproductions across all six pairs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.bounded_branch_reproduction import (  # noqa: E402
    compare_all,
    write_comparison,
)
from fastlio2_adapter.day6_semantic_observation import (  # noqa: E402
    load_observation_records,
)
from fastlio2_adapter.experiment_a_stage_classifier import (  # noqa: E402
    load_records,
)
from fastlio2_adapter.formal_trajectory_clustering import (  # noqa: E402
    cluster_formal_trajectories,
    write_clusters,
)


RUN_IDS = tuple(
    f"multihyp_day6_branch_repro_r{index}" for index in range(1, 5)
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    root = args.runtime_root.expanduser().resolve()
    observations = {}
    stage = {}
    integrity = {}
    for run_id in RUN_IDS:
        observations[run_id], integrity[run_id] = load_observation_records(
            root / run_id / "observation_records_v3.bin"
        )
        stage[run_id] = load_records(
            root / run_id / "experiment_a_stage_hash_records_v2.json"
        )
    result = compare_all(
        run_ids=RUN_IDS,
        observations=observations,
        stage_records=stage,
    )
    output = args.output_dir.expanduser().resolve()
    write_comparison(result, output)
    clusters = cluster_formal_trajectories(observations)
    write_clusters(clusters, output)
    (output / "observation_integrity_summary.json").write_text(
        json.dumps(integrity, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "pair_count": len(result["semantic_summaries"]),
                "cluster_count": clusters["cluster_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

