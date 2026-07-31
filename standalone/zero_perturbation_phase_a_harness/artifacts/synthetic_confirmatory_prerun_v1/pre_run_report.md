# Synthetic Confirmatory Pre-Run Qualification v1

This artifact contains qualification evidence only. It contains no Confirmatory snapshot, trial result, or performance estimate.

- `SYNTHETIC_CONFIRMATORY_PRE_RUN_QUALIFICATION_PASS = true`
- `CONFIRMATORY_RUN_AUTHORIZED = true`
- `SYNTHETIC_CONFIRMATORY_EXECUTED = false`
- `SYNTHETIC_CONFIRMATORY_COMPLETE = false`
- `SYNTHETIC_CONFIRMATORY_PASS = NOT_EVALUATED`
- `REAL_DATA_RUN_AUTHORIZED = false`
- `MEASUREMENT_PAPER_MAINLINE_AUTHORIZED = false`

## Zero formal-execution counters

- `CONFIRMATORY_RNG_INSTANTIATION_COUNT = 0`
- `CONFIRMATORY_SNAPSHOT_GENERATION_COUNT = 0`
- `CONFIRMATORY_BACKEND_EXECUTION_COUNT = 0`
- `CONFIRMATORY_TRIAL_RESULT_COUNT = 0`
- `NATIVE_EXECUTION_COUNT = 0`

## Frozen plan

- Planned snapshots/trials: `595 / 1190`
- Duplicate snapshot/trial IDs: `0 / 0`
- Pairing violations: `0`

## Seed-free execution-chain fixture

- Fixture snapshots/trials: `3 / 6`
- Fixture qualification: `True`

## Formal dry-run

- Enumerated snapshots/trials: `595 / 1190`
- Confirmatory RNG, snapshot generation, backend execution, trial results, and STARTED events: `0 / 0 / 0 / 0 / 0`

## Interpretation boundary

This qualification authorizes a later formal run using the exact frozen manifest. It does not execute or evaluate Synthetic Confirmatory science.

## Evidence inventory

- `protocol_binding.json`
- `gate_contract_audit.json`
- `seed_provenance_audit.json`
- `plan_audit.json`
- `frozen_model_audit.json`
- `frozen_model_prediction_crosscheck.json`
- `fixture_regression_report.json`
- `dry_run_report.json`
- `implementation_manifest.json`
- `test_report.json`
- `final_decision.json`
- `run_manifest.json`
- `SHA256SUMS`
- `fixture_publication/` (complete seed-free 3/6 fixture publication)
