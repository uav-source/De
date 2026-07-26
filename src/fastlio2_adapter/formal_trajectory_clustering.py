"""Cluster four runs by complete semantic-observation checksum sequence."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .day6_semantic_observation import semantic_observation_checksum


class FormalTrajectoryClusteringError(ValueError):
    """Formal trajectory input violates the fixed four-run contract."""


def trajectory_checksum(
    records: Sequence[Mapping[str, Any]],
) -> tuple[str, list[str]]:
    if len(records) != 487:
        raise FormalTrajectoryClusteringError(
            "formal trajectory must contain 487 observations"
        )
    sequence = [
        semantic_observation_checksum(record, index)
        for index, record in enumerate(records)
    ]
    digest = hashlib.sha256()
    for checksum in sequence:
        digest.update(checksum.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), sequence


def cluster_formal_trajectories(
    observations: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    if len(observations) != 4:
        raise FormalTrajectoryClusteringError(
            "exactly four formal trajectories are required"
        )
    checksums: dict[str, str] = {}
    sequences: dict[str, list[str]] = {}
    for run_id, records in observations.items():
        checksums[run_id], sequences[run_id] = trajectory_checksum(records)
    grouped: dict[str, list[str]] = {}
    for run_id, checksum in checksums.items():
        grouped.setdefault(checksum, []).append(run_id)
    clusters = []
    for index, checksum in enumerate(sorted(grouped), start=1):
        runs = sorted(grouped[checksum])
        clusters.append(
            {
                "cluster_id": f"cluster_{index}",
                "formal_trajectory_checksum": checksum,
                "runs": runs,
                "size": len(runs),
            }
        )
    pairs = []
    run_ids = list(observations)
    for left_index, left in enumerate(run_ids):
        for right in run_ids[left_index + 1 :]:
            pairs.append(
                {
                    "pair": f"{left}-{right}",
                    "left_run": left,
                    "right_run": right,
                    "same_formal_trajectory":
                        sequences[left] == sequences[right],
                }
            )
    return {
        "schema_version": "formal_trajectory_clusters_v1",
        "run_count": 4,
        "unique_formal_trajectory_count": len(grouped),
        "cluster_count": len(clusters),
        "clusters": clusters,
        "per_run_trajectory_checksum": checksums,
        "pairs": pairs,
        "formal_trajectory_clustering_pass": len(pairs) == 6,
        "largest_cluster_is_not_claimed_correct": True,
    }


def write_clusters(result: Mapping[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "formal_trajectory_clusters.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    membership = []
    for cluster in result["clusters"]:
        for run_id in cluster["runs"]:
            membership.append(
                {
                    "run_id": run_id,
                    "cluster_id": cluster["cluster_id"],
                    "cluster_size": cluster["size"],
                    "formal_trajectory_checksum":
                        cluster["formal_trajectory_checksum"],
                }
            )
    with (
        output_dir / "formal_trajectory_cluster_membership.csv"
    ).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(membership[0]))
        writer.writeheader()
        writer.writerows(membership)

