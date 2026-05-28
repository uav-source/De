# Day 30 Final Release Notes

## Scope

This release candidate is scoped as a diagnostic benchmark / failure-analysis package for LiDAR-Inertial degeneracy analysis.
It is not a validated Degen-LIO estimator method.

## Allowed Claims

- The repository provides a reproducible synthetic diagnostic benchmark package.
- The package documents legacy bias, unbiased toy-probe protocols, metric-validity stress tests, and No-Go gate evidence.
- F01 and F03 are generated from source artifacts, not placeholders.

## Forbidden Claims

- Do not claim a validated Degen-LIO estimator method.
- Do not claim weak-subspace update authorization.
- Do not claim robust ODI drift prediction.
- Do not claim toy_lio is a real LIO estimator.

## Reproduction Commands

For full staged reproduction, run the Day15-Day30 scripts listed in README.
The short command block below is only a final audit shortcut, not the full chain.

```bash
python3 scripts/check_env.py
python3 -m pytest -q
bash scripts/reproduce_day14.sh --run
python3 scripts/22_day29_safe_figures.py --config configs/validation/day29_safe_figures.yaml
python3 scripts/23_day30_final_package_review.py --config configs/validation/day30_final_package_review.yaml
```

## Included Artifacts

- Source code, configs, scripts, tests, README, docs, reports, selected results/day30 tables and manifests.
- Paper skeleton, generated tables, real F01/F03 figures, caption banks, and release docs.

## Excluded Paths

- `.git`
- `.pytest_cache`
- `__pycache__`
- other local caches or temporary build products.

## Manual Checks Before Release

- Run full local pytest and confirm success.
- Perform a clean archive dry-run with `git archive` or an `rsync --exclude` staging directory.
- Inspect the archive contents before sharing.

## Known Limitations

- Diagnostic package status: ready_for_draft.
- Synthetic-only evidence remains a limitation.
- The method update gate remains closed.
- ODI robust drift prediction remains unvalidated.
