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
