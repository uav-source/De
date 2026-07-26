import importlib.util
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("frozen_clips", ROOT / "scripts/49_prepare_day5_frozen_replay_clips.py")
M = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(M)


def metadata(lidar=2, imu=3, topics=None):
    return {"topics": topics or list(M.TOPICS), "topic_counts": {M.TOPICS[0]: lidar, M.TOPICS[1]: imu}, "message_count": lidar + imu}


def test_source_sha_mismatch_fails(tmp_path):
    path = tmp_path / "source.bag"; path.write_bytes(b"bag")
    with pytest.raises(M.ClipError, match="SHA mismatch"):
        M.verify_source(path, "0" * 64)


def test_clip_contains_exactly_two_topics():
    M.validate_clip_metadata(metadata())
    with pytest.raises(M.ClipError, match="exactly"):
        M.validate_clip_metadata(metadata(topics=[*M.TOPICS, "/extra"]))


@pytest.mark.parametrize(("lidar", "imu", "message"), [(0, 2, "LiDAR"), (2, 0, "IMU"), (0, 0, "LiDAR")])
def test_empty_or_missing_required_topic_fails(lidar, imu, message):
    with pytest.raises(M.ClipError, match=message):
        M.validate_clip_metadata(metadata(lidar, imu))


def test_clip_is_read_only(tmp_path):
    path = tmp_path / "clip.bag"; path.write_bytes(b"clip"); os.chmod(path, 0o444)
    assert M.clip_is_read_only(path) is True


def test_existing_clip_cannot_be_regenerated(tmp_path):
    path = tmp_path / "clip.bag"; path.write_bytes(b"clip")
    with pytest.raises(M.ClipError, match="refusing to regenerate"):
        M.ensure_new_output(path)


def test_clip_sha_change_is_detected(tmp_path):
    path = tmp_path / "clip.bag"; path.write_bytes(b"first")
    before = M.sha256_file(path); path.write_bytes(b"second")
    assert M.sha256_file(path) != before
