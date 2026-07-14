import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cleanup_manifest_has_required_audit_fields():
    manifest = json.loads((ROOT / "artifacts/current/cleanup_manifest.json").read_text(encoding="utf-8"))
    required = {
        "baseline_commit", "cleanup_commit", "deleted_tracked_file_count",
        "deleted_untracked_file_count", "deleted_bytes", "preserved_artifact_count",
        "preserved_artifact_sha256", "remaining_workspace_bytes",
        "remaining_tracked_data_files", "remaining_cache_files",
        "legacy_import_reference_count", "pytest_result",
    }
    assert required <= set(manifest)
    assert manifest["remaining_workspace_bytes"] < 30 * 1024 * 1024
    assert manifest["remaining_tracked_data_files"] == 0
    assert manifest["remaining_cache_files"] == 0
