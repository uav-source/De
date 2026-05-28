# Release Cleanup Policy

The formal release archive must exclude:

- `.git`
- `.pytest_cache`
- `__pycache__`
- matplotlib/font caches
- local editor caches

Do not delete user files during cleanup planning. Use a clean archive command such as `git archive` or `rsync --exclude` to produce a release bundle.

Raw trajectory files are generated artifacts. Prefer rebuilding them with scripts unless the release explicitly includes them and records their provenance.

Key `results/day30` CSV tables and manifests should be either committed with `git add -f` or documented as rebuildable outputs.
