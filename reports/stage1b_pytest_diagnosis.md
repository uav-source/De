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

- Complete test count: pending final Stage 1b validation
- Complete test duration: pending final Stage 1b validation
- Slowest 10 tests: pending final Stage 1b validation
