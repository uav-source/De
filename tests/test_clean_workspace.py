from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from clean_workspace import CleanupSafetyError, run_cleanup, validate_target  # noqa: E402


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "data/metric_redesign_stage1c").mkdir(parents=True)
    (root / "data/metric_redesign_stage1c/generated.bin").write_bytes(b"generated")
    (root / "src/pkg/__pycache__").mkdir(parents=True)
    (root / "src/pkg/__pycache__/module.pyc").write_bytes(b"cache")
    (root / "src/pkg/module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "artifacts/history/frozen").mkdir(parents=True)
    (root / "artifacts/history/frozen/evidence.json").write_text("{}\n", encoding="utf-8")
    return root


def test_default_cleanup_is_dry_run(tmp_path):
    root = make_repo(tmp_path)
    summary = run_cleanup(root, apply=False)
    assert summary.applied is False
    assert (root / "data/metric_redesign_stage1c/generated.bin").exists()
    assert (root / "src/pkg/__pycache__/module.pyc").exists()


def test_apply_deletes_only_generated_data_and_cache(tmp_path):
    root = make_repo(tmp_path)
    summary = run_cleanup(root, apply=True)
    assert summary.deleted_file_count == 2
    assert not (root / "data/metric_redesign_stage1c").exists()
    assert not (root / "src/pkg/__pycache__").exists()
    assert (root / "src/pkg/module.py").exists()
    assert (root / "artifacts/history/frozen/evidence.json").exists()


def test_symbolic_link_escape_is_rejected(tmp_path):
    root = make_repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "data/minibench"
    link.parent.mkdir(exist_ok=True)
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(CleanupSafetyError, match="escapes repository"):
        run_cleanup(root, apply=True)


def test_repository_external_target_is_rejected(tmp_path):
    root = make_repo(tmp_path)
    with pytest.raises(CleanupSafetyError, match="outside repository"):
        validate_target(root, tmp_path / "outside.log")
