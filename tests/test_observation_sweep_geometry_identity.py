from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1b import generate_or_validate_sequence, load_yaml, make_spec, sha256_file  # noqa: E402
from stage1b_helpers import stage1b_paths  # noqa: E402


def test_observation_levels_have_identical_gt_planes_and_axis(tmp_path):
    common = load_yaml(stage1b_paths()["common"])
    checksums = []
    for level, probability in [("O1", 1.0), ("O2", 0.4), ("O3", 0.1), ("O4", 0.02)]:
        spec = make_spec(common["scene"], "observation", level, 101, "train", active_patch_count=16, keep_probability=probability)
        sequence_dir = tmp_path / level
        generate_or_validate_sequence(sequence_dir, spec)
        checksums.append(tuple(sha256_file(sequence_dir / name) for name in ["gt.tum", "planes.csv", "axis.csv"]))
    assert len(set(checksums)) == 1
