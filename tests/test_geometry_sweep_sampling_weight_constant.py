from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.synthetic_pipeline_common import load_yaml, make_spec  # noqa: E402
from minibench.scene_generator import generate_straight_tunnel  # noqa: E402
from stage1c_helpers import paths  # noqa: E402


def test_geometry_sweep_all_plane_sampling_weights_are_one():
    common = load_yaml(paths()["common"])
    for level, count in [("L1", 12), ("L2", 7), ("L3", 3), ("L4", 1)]:
        sequence = generate_straight_tunnel(make_spec(common["scene"], "geometry", level, 101, "train", active_patch_count=count))
        assert {plane.sampling_weight for plane in sequence.planes} == {1.0}
        assert sequence.metadata["sampling_weight_values"] == [1.0]
