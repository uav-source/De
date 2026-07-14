from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]


def stage1b_paths() -> Dict[str, Path]:
    return {
        "common": ROOT / "configs/redesign/stage1b_common.yaml",
        "geometry": ROOT / "configs/redesign/stage1b_geometry_sweep.yaml",
        "observation": ROOT / "configs/redesign/stage1b_observation_sweep.yaml",
        "detector": ROOT / "configs/detector/odi_stage1b.yaml",
        "motion": ROOT / "configs/toy_lio/motion_surrogate_stage1b.yaml",
    }


def make_observation_sequence(tmp_path: Path) -> Path:
    from eval.metric_redesign_stage1b import generate_or_validate_sequence, load_yaml, make_spec

    common = load_yaml(stage1b_paths()["common"])
    spec = make_spec(
        common["scene"],
        "observation",
        "O1",
        101,
        "train",
        active_patch_count=int(common["scene"]["master_axial_patch_pool_size"]),
        keep_probability=1.0,
    )
    sequence_dir = tmp_path / str(spec["sequence_id"])
    generate_or_validate_sequence(sequence_dir, spec)
    return sequence_dir
