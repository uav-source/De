#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGING_DIR="${STAGING_DIR:-/tmp/degen_lio_release_dryrun}"

cat <<'MSG'
Day 31 release dry-run helper

This helper does not delete user files, upload artifacts, or create a formal release.
Before executing a staging copy, confirm full local pytest passed:

  python3 -m pytest -q

MSG

EXCLUDES=(
  "--exclude" ".git"
  "--exclude" ".pytest_cache"
  "--exclude" "__pycache__"
  "--exclude" ".mypy_cache"
  "--exclude" ".ruff_cache"
  "--exclude" "fontlist-*.json"
)

if [[ "${1:-}" != "--execute" ]]; then
  cat <<MSG
Print-only dry-run mode.

Recommended clean archive command:
  git -C "$ROOT_DIR" archive --format=tar.gz --output /tmp/degen_lio_diagnostic_benchmark_HEAD.tar.gz HEAD

Recommended staging command after pytest confirmation:
  CONFIRM_PYTEST_PASSED=1 bash scripts/release_dryrun.sh --execute

Archive content inspection command:
  tar -tzf /tmp/degen_lio_diagnostic_benchmark_HEAD.tar.gz | sort | less

Excluded path policy:
  .git, .pytest_cache, __pycache__, local caches, editor caches
MSG
  exit 0
fi

if [[ "${CONFIRM_PYTEST_PASSED:-0}" != "1" ]]; then
  echo "ERROR: set CONFIRM_PYTEST_PASSED=1 only after python3 -m pytest -q completed locally." >&2
  exit 2
fi

mkdir -p "$STAGING_DIR"
echo "Staging dry-run copy into: $STAGING_DIR"
echo "This command will not delete files from the repository."

rsync -a --dry-run "${EXCLUDES[@]}" "$ROOT_DIR/" "$STAGING_DIR/"

cat <<MSG

Dry-run complete. No files were copied because rsync used --dry-run.
To inspect a real staging copy, remove --dry-run manually after reviewing the command.
Do not publish an archive until the file list is manually inspected.
MSG
