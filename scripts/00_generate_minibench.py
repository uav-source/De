#!/usr/bin/env python3
"""Generate the four Day 1-14 minimum geometry scenes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.scene_generator import (  # noqa: E402
    generate_curved_tunnel,
    generate_open_control,
    generate_repetitive_tunnel,
    generate_straight_tunnel,
    load_scene_config,
    save_sequence,
)


DEFAULT_CONFIGS = [
    ROOT / "configs/minibench/OC-L0-S01-M1.yaml",
    ROOT / "configs/minibench/ST-L3-S01-M1.yaml",
    ROOT / "configs/minibench/CT-L2-S01-M2.yaml",
    ROOT / "configs/minibench/RT-L4-S01-M1.yaml",
]


def build_sequence(config_path: Path):
    config = load_scene_config(config_path)
    family = config["scene_family"]
    if family == "OC":
        return generate_open_control(config)
    if family == "ST":
        return generate_straight_tunnel(config)
    if family == "CT":
        return generate_curved_tunnel(config)
    if family == "RT":
        return generate_repetitive_tunnel(config)
    raise ValueError(f"Unsupported scene_family {family!r} in {config_path}")


def generate_one(config_path: Path, out_dir: Path) -> None:
    sequence = build_sequence(config_path)
    save_sequence(sequence, out_dir)
    print(
        f"generated {sequence.sequence_id}: frames={sequence.gt_poses.shape[0]} "
        f"planes={len(sequence.planes)} features={sequence.feature_points.shape[0]} out={out_dir}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Path to one minibench YAML config.")
    parser.add_argument("--out", type=Path, help="Output directory for one generated sequence.")
    parser.add_argument("--all", action="store_true", help="Generate all four core benchmark sequences.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.all:
        for config_path in DEFAULT_CONFIGS:
            out_dir = ROOT / "data/minibench" / config_path.stem
            generate_one(config_path, out_dir)
        return 0

    if args.config is None or args.out is None:
        raise SystemExit("--config and --out are required unless --all is used")

    generate_one(args.config, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
