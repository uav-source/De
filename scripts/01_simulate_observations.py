#!/usr/bin/env python3
"""Generate Day 5 point-to-plane Jacobian observations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.observation_simulator import (  # noqa: E402
    save_observations,
    simulate_sequence_observations,
)


DEFAULT_SEQUENCES = [
    ROOT / "data/minibench/OC-L0-S01-M1",
    ROOT / "data/minibench/ST-L3-S01-M1",
    ROOT / "data/minibench/CT-L2-S01-M2",
    ROOT / "data/minibench/RT-L4-S01-M1",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seq", type=Path, help="Generated sequence directory.")
    parser.add_argument("--config", type=Path, required=True, help="Detector config path.")
    parser.add_argument("--all", action="store_true", help="Simulate all four core benchmark sequences.")
    parser.add_argument("--sensor-seed", type=int, help="Override the sensor sampling/noise seed.")
    return parser.parse_args()


def simulate_one(sequence_dir: Path, config_path: Path, sensor_seed=None) -> None:
    output_path = sequence_dir / "observations.npz"
    observations = simulate_sequence_observations(sequence_dir, config_path, sensor_seed=sensor_seed)
    save_observations(observations, output_path)
    packed_J = observations["packed_J"]
    print(
        f"generated observations: seq={sequence_dir.name} frames={packed_J.shape[0]} "
        f"points_per_frame={packed_J.shape[1]} out={output_path}"
    )


def main() -> int:
    args = parse_args()
    if args.all:
        for sequence_dir in DEFAULT_SEQUENCES:
            simulate_one(sequence_dir, args.config, args.sensor_seed)
        return 0
    if args.seq is None:
        raise SystemExit("--seq is required unless --all is used")
    simulate_one(args.seq, args.config, args.sensor_seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
