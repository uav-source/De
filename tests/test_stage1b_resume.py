from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1b import prepare_run_directories  # noqa: E402


def test_resume_preserves_existing_artifacts_and_nonresume_refuses(tmp_path):
    data = tmp_path / "data/run"
    results = tmp_path / "results/run"
    prepare_run_directories(data, results, resume=False, overwrite=False)
    sentinel = results / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    prepare_run_directories(data, results, resume=True, overwrite=False)
    assert sentinel.read_text(encoding="utf-8") == "keep"
    with pytest.raises(FileExistsError):
        prepare_run_directories(data, results, resume=False, overwrite=False)
