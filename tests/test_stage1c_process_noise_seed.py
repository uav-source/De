from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minibench.motion_simulator import derive_process_noise_seed  # noqa: E402


def test_stage1c_seed_is_stable_and_has_no_level_argument():
    first = derive_process_noise_seed("stage1c_geometry", 606, 33, 2001, "m1")
    same = derive_process_noise_seed("stage1c_geometry", 606, 33, 2001, "m1")
    assert first == same
    assert isinstance(first, int) and 0 <= first < 2**64
