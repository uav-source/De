from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def paths():
    return {
        "common": ROOT / "configs/redesign/stage1c_common.yaml",
        "quick": ROOT / "configs/redesign/stage1c_quick.yaml",
        "development": ROOT / "configs/redesign/stage1c_development.yaml",
        "test": ROOT / "configs/redesign/stage1c_test.yaml",
        "detector": ROOT / "configs/detector/odi_stage1c.yaml",
        "motion": ROOT / "configs/toy_lio/motion_surrogate_stage1c.yaml",
    }


def make_observation_sequence(tmp_path: Path) -> Path:
    from eval.synthetic_pipeline_common import generate_or_validate_sequence, load_yaml, make_spec

    common = load_yaml(paths()["common"])
    spec = make_spec(
        common["scene"],
        "observation",
        "O1",
        101,
        "development",
        active_patch_count=int(common["scene"]["master_axial_patch_pool_size"]),
        keep_probability=1.0,
    )
    sequence_dir = tmp_path / str(spec["sequence_id"])
    generate_or_validate_sequence(sequence_dir, spec)
    return sequence_dir
