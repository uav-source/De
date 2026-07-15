import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/audit_stage1_freeze.py"
SPEC = importlib.util.spec_from_file_location("audit_stage1_freeze", SCRIPT_PATH)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def build(paths, root, excluded_paths=()):
    return AUDIT.build_manifest(paths, root, excluded_paths=excluded_paths)[0]


def test_file_sorting_is_stable(tmp_path):
    (tmp_path / "z.txt").write_text("z", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested/a.txt").write_text("a", encoding="utf-8")

    manifest = build([tmp_path], tmp_path)

    assert [item["relative_path"] for item in manifest["files"]] == [
        "nested/a.txt",
        "z.txt",
    ]


def test_two_runs_have_identical_hash_outputs(tmp_path):
    audited = tmp_path / "audited"
    audited.mkdir()
    (audited / "sample.txt").write_text("stable", encoding="utf-8")
    json_output = audited / "manifest.json"
    sha_output = audited / "SHA256SUMS"
    args = [
        str(audited),
        "--repo-root",
        str(tmp_path),
        "--json-output",
        str(json_output),
        "--sha256-output",
        str(sha_output),
    ]

    assert AUDIT.main(args) == 0
    first_json = json_output.read_bytes()
    first_sha = sha_output.read_bytes()
    assert AUDIT.main(args) == 0

    assert json_output.read_bytes() == first_json
    assert sha_output.read_bytes() == first_sha


def test_file_modification_changes_hash(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("before", encoding="utf-8")
    before = build([tmp_path], tmp_path)["files"][0]["sha256"]

    target.write_text("after", encoding="utf-8")
    after = build([tmp_path], tmp_path)["files"][0]["sha256"]

    assert after != before


def test_empty_directory_is_valid(tmp_path):
    manifest, readable = AUDIT.build_manifest([tmp_path], tmp_path)

    assert readable is True
    assert manifest["file_count"] == 0
    assert manifest["total_size_bytes"] == 0
    assert manifest["inputs"][0]["missing"] is False


def test_missing_path_is_marked(tmp_path):
    missing = tmp_path / "absent"

    manifest = build([missing], tmp_path)

    assert manifest["inputs"] == [
        {
            "relative_path": "absent",
            "missing": True,
            "file_count": 0,
            "size_bytes": 0,
        }
    ]


def test_cache_git_and_pyc_files_are_ignored(tmp_path):
    for directory in ["__pycache__", ".git", ".pytest_cache", "results", "data"]:
        ignored = tmp_path / directory
        ignored.mkdir()
        (ignored / "ignored.txt").write_text("ignored", encoding="utf-8")
    (tmp_path / "ignored.pyc").write_bytes(b"ignored")
    (tmp_path / "kept.txt").write_text("kept", encoding="utf-8")

    manifest = build([tmp_path], tmp_path)

    assert [item["relative_path"] for item in manifest["files"]] == ["kept.txt"]


def test_output_paths_are_repository_relative(tmp_path):
    directory = tmp_path / "source"
    directory.mkdir()
    (directory / "file.txt").write_text("content", encoding="utf-8")

    manifest = build([directory], tmp_path)

    assert manifest["inputs"][0]["relative_path"] == "source"
    assert manifest["files"][0]["relative_path"] == "source/file.txt"
    assert not Path(manifest["files"][0]["relative_path"]).is_absolute()


def test_audit_does_not_modify_input_files(tmp_path):
    target = tmp_path / "sample.bin"
    target.write_bytes(b"unchanged")
    before_bytes = target.read_bytes()
    before_stat = target.stat()

    build([tmp_path], tmp_path)

    after_stat = target.stat()
    assert target.read_bytes() == before_bytes
    assert after_stat.st_size == before_stat.st_size
    assert after_stat.st_mtime_ns == before_stat.st_mtime_ns


def test_read_failure_returns_nonzero(tmp_path, monkeypatch):
    target = tmp_path / "unreadable.txt"
    target.write_text("content", encoding="utf-8")
    json_output = tmp_path.parent / "read_failure_manifest.json"
    sha_output = tmp_path.parent / "read_failure_sha256.txt"
    original_hash_file = AUDIT._hash_file

    def fail_for_target(path):
        if path == target:
            raise PermissionError("simulated read denial")
        return original_hash_file(path)

    monkeypatch.setattr(AUDIT, "_hash_file", fail_for_target)
    exit_code = AUDIT.main(
        [
            str(tmp_path),
            "--repo-root",
            str(tmp_path),
            "--json-output",
            str(json_output),
            "--sha256-output",
            str(sha_output),
        ]
    )

    manifest = json.loads(json_output.read_text(encoding="utf-8"))
    assert exit_code != 0
    assert manifest["errors"][0]["relative_path"] == "unreadable.txt"
