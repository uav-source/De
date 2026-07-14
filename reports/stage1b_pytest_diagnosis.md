# Stage 1b pytest diagnosis

## Baseline observation

The requested historical "full pytest hangs" symptom was not reproducible on the Stage 1 base commit `5c9802c`. Before Stage 1b code changes:

```bash
pytest --collect-only -q
pytest -vv --durations=50
```

collected 136 tests and completed all 136 in 28.33 seconds. There was therefore no current stuck test, leaked pool, subprocess, background thread, file lock, or order-dependent failure to remove. Claiming a specific historical root cause would be unsupported.

## Root-cause conclusion

Current root cause: **no hang exists on the reproducible Stage 1 baseline**. The likely historical symptom had already been removed or was environment-specific before this branch. Stage 1b adds `faulthandler_timeout = 120` to `pytest.ini` so any future stall emits Python stacks without requiring `pytest-timeout`. New figure code closes every matplotlib figure, worker pools use context managers, NPZ readers close their file handles, and Stage 1b tests use isolated temporary paths.

## Validation commands

Before-change reproduction:

```bash
pytest --collect-only -q
pytest -vv --durations=50
```

After-change validation:

```bash
pytest -q
```

## Final result

- Exact final command: `pytest -q`
- Complete test count: 150 passed
- Complete test duration: 30.84 seconds
- A second diagnostic run, `pytest -q --durations=10`, also completed 150 tests in 30.20 seconds.

Slowest 10 items in the diagnostic run:

1. `test_day8_summary_matches_recomputed_tum_errors` setup: 6.21 s
2. `test_stage1b_pipeline_quick`: 4.68 s
3. `test_metric_redesign_stage1_pipeline`: 3.83 s
4. `test_observation_sweep_nested_retention`: 2.10 s
5. `test_day29_generates_real_figures_and_safety_artifacts`: 1.60 s
6. `test_day18_script_runs_and_preserves_prior_outputs`: 1.21 s
7. `test_sequence_observations_npz_contract_shapes`: 0.98 s
8. `test_day17_script_runs_and_preserves_day14_day15_day16_inputs`: 0.89 s
9. `test_day18_script_reports_missing_day17_raw_trajectory`: 0.78 s
10. `test_day21_permutation_seed_is_fixed`: 0.58 s
