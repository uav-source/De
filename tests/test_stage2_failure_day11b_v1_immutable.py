import hashlib

from eval.stage2_failure_day11b_provenance import (
    result_tree_manifest,
    write_v1_immutable_after_evidence,
)


def test_v1_tree_change_is_detected(tmp_path):
    root = tmp_path / "root"
    run = root / "results/v1"
    run.mkdir(parents=True)
    target = run / "result.json"
    target.write_text("before", encoding="utf-8")
    before = tmp_path / "before.txt"
    before.write_bytes(result_tree_manifest(root, run))
    target.write_text("after", encoding="utf-8")
    result = write_v1_immutable_after_evidence(
        root, run, before, tmp_path / "after.txt", tmp_path / "after.digest"
    )
    assert result["day11b_v1_result_tree_unchanged"] is False
    assert result["v1_result_tree_digest_before"] != result["v1_result_tree_digest_after"]


def test_unchanged_v1_tree_passes(tmp_path):
    root = tmp_path / "root"
    run = root / "results/v1"
    run.mkdir(parents=True)
    (run / "result.json").write_text("same", encoding="utf-8")
    before = tmp_path / "before.txt"
    before.write_bytes(result_tree_manifest(root, run))
    result = write_v1_immutable_after_evidence(
        root, run, before, tmp_path / "after.txt", tmp_path / "after.digest"
    )
    assert result["day11b_v1_result_tree_unchanged"] is True
    assert result["v1_result_tree_digest_before"] == hashlib.sha256(before.read_bytes()).hexdigest()
