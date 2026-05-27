from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs" / "minibench"

EXPECTED_CONFIGS = {
    "OC-L0-S01-M1.yaml": {
        "sequence_id": "OC-L0-S01-M1",
        "scene_family": "OC",
        "difficulty": "L0",
        "frames": 200,
        "trajectory": "open_loop",
        "expected_degeneracy": "low",
    },
    "ST-L3-S01-M1.yaml": {
        "sequence_id": "ST-L3-S01-M1",
        "scene_family": "ST",
        "difficulty": "L3",
        "frames": 240,
        "trajectory": "straight_axis_motion",
        "expected_degeneracy": "high_axis_translation",
    },
    "CT-L2-S01-M2.yaml": {
        "sequence_id": "CT-L2-S01-M2",
        "scene_family": "CT",
        "difficulty": "L2",
        "frames": 220,
        "trajectory": "curved_centerline_motion",
        "expected_degeneracy": "medium_local_axis",
    },
    "RT-L4-S01-M1.yaml": {
        "sequence_id": "RT-L4-S01-M1",
        "scene_family": "RT",
        "difficulty": "L4",
        "frames": 260,
        "trajectory": "straight_axis_motion",
        "expected_degeneracy": "high_axis_translation_and_association_ambiguity",
    },
}


def load_config(name):
    with (CONFIG_DIR / name).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def vector_norm(values):
    return sum(float(value) ** 2 for value in values) ** 0.5


def test_exact_four_minibench_configs_exist():
    names = sorted(path.name for path in CONFIG_DIR.glob("*.yaml"))

    assert names == sorted(EXPECTED_CONFIGS)


def test_minibench_configs_freeze_required_fields():
    for name, expected in EXPECTED_CONFIGS.items():
        config = load_config(name)
        for key, value in expected.items():
            assert config[key] == value

        assert config["seed_id"] == "S01"
        assert config["random_seed"] == 42
        assert config["motion_id"] in {"M1", "M2"}
        assert config["dt_s"] > 0
        assert "scientific_role" in config
        assert "scene" in config
        assert "motion" in config
        assert "sensor_stub" in config


def test_straight_and_repetitive_axis_are_unit_x():
    for name in ["ST-L3-S01-M1.yaml", "RT-L4-S01-M1.yaml", "OC-L0-S01-M1.yaml"]:
        axis = load_config(name)["axis"]
        assert vector_norm(axis) == 1.0
        assert axis == [1.0, 0.0, 0.0]


def test_curved_tunnel_uses_local_axis_contract():
    config = load_config("CT-L2-S01-M2.yaml")

    assert config["axis"] is None
    assert config["local_axis"] == "centerline_tangent"
    assert config["curve_radius_m"] == 40
    assert config["arc_length_m"] == 100


def test_straight_tunnel_normals_preserve_axis_weakness_contract():
    config = load_config("ST-L3-S01-M1.yaml")

    assert config["scene"]["dominant_normal_x_abs_max"] <= 0.05
    for normal in config["scene"]["side_wall_normals"] + config["scene"]["floor_ceiling_normals"]:
        assert abs(normal[0]) == 0.0


def test_minibench_spec_lists_required_outputs():
    text = (ROOT / "docs" / "minibench_spec.md").read_text(encoding="utf-8")

    for filename in [
        "gt.tum",
        "axis.csv",
        "planes.csv",
        "scene_metadata.json",
        "observations.npz",
        "pose_init.tum",
        "pose_est_toy.tum",
        "metrics.csv",
    ]:
        assert filename in text

