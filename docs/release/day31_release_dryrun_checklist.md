# Day 31 Release Dry-Run Checklist

## Full Local Pytest Command

Run this immediately before preparing any public archive:

```bash
python3 -m pytest -q
```

Do not mark release readiness as pass unless this command completes locally.

## Clean Archive Dry-Run Command

Default safe command:

```bash
bash scripts/release_dryrun.sh
```

The default mode prints a dry-run plan and does not create, delete, upload, or publish files.

Optional local staging command after confirming pytest:

```bash
CONFIRM_PYTEST_PASSED=1 bash scripts/release_dryrun.sh --execute
```

## Expected Excluded Paths

The release archive or staging directory must exclude:

- `.git`
- `.pytest_cache`
- `__pycache__`
- matplotlib/font caches
- editor caches
- temporary local build products

## Manual Inspection Steps

1. Confirm `python3 -m pytest -q` completed on the release machine.
2. Run the dry-run script in default print-only mode.
3. If needed, run the explicit staging mode with `CONFIRM_PYTEST_PASSED=1`.
4. Inspect the generated file list.
5. Confirm no cache directories or local repository internals are included.
6. Confirm README and release notes still state the diagnostic benchmark scope.

## Final Allowed Claims

- The repository is a diagnostic benchmark / failure-analysis package.
- F01/F03 are generated from source artifacts.
- The package preserves negative metric-validity evidence and claim boundaries.
- The package is ready for draft/release review only after manual pytest and archive inspection.

## Final Forbidden Claims

- A validated Degen-LIO estimator method is provided.
- Weak-subspace update is authorized.
- Robust ODI drift prediction is validated.
- toy_lio is a real LIO estimator.
- Joint risk features are validated drift predictors.
