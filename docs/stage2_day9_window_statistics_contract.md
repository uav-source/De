# Stage 2 Failure-Mechanism Diagnosis — Day 9 Window Statistics Contract

## Purpose and scope

Day 9 has one purpose: transform the Day 8 per-frame signed weak-innovation scores into strictly causal diagnostic window statistics. It computes a window mean, median, energy, sign balance and runs, two-sided CUSUM, lag-1 autocorrelation, and population-moment skewness. These statistics are foundations for later failure-mechanism analysis; Day 9 does not decide whether coherent bias has been detected.

The primary signal is `weak_innovation_z_huber`. It describes directional score remaining after the estimator's existing robust weighting. The auxiliary diagnostic signal is `weak_innovation_z_raw`, retained only to expose the effect of Huber weighting. Day 9 never chooses between them and never changes the estimator from their values.

Day 9 reads only `frame_diagnostics_online.csv`. It does not read the Day 8 offline evaluation CSV, a ground-truth pose or axis, a scene label, an oracle direction, or a future frame.

## Valid input and hard reset

A frame is a valid statistic input exactly when

```text
weak_direction_valid
and weak_innovation_valid
and primary_direction_stable
and isfinite(weak_innovation_z_raw)
and isfinite(weak_innovation_z_huber).
```

Neither `degeneracy_triggered` nor `actionable_direction` is required. Both remain in the output, together with ODI and eigengap, so normal and non-actionable frames remain available for diagnosis.

An invalid frame clears both windows, both CUSUM states, every same-sign run, and the consecutive-valid count. Its statistics are invalid and represented by NaN, while counts are zero. The next valid frame begins a new segment. Skipping an invalid frame and joining the values on either side would falsely claim temporal continuity, so cross-invalid windows are forbidden.

## Grouping, order, and causality

State is owned by the exact tuple

```text
run_id, sequence_id, sweep, level, stress,
geometry_seed, sensor_seed, process_seed, method.
```

Methods, sequences, stress cases, and seeds never share a window or CUSUM. Within each group, `frame_index` and `timestamp` must both increase strictly. Duplicate or regressing rows are errors; the pipeline does not sort malformed input and silently continue.

Every window is left aligned:

```text
W_t = {z_(t-n+1), ..., z_t}.
```

It contains only values already observed at frame `t`. Appending future rows cannot change any existing output row. The runtime manifest records a prefix-equivalence audit, and the tests exercise every prefix.

## Frozen Quick configuration

Day 9 Quick uses a window size of 5, CUSUM reference `k=0.5`, sign-zero epsilon `1e-12`, and moment epsilon `1e-12`. These are engineering-fixture parameters. They are not a detection threshold, a Stage 3 lock, or a claim of optimality.

Partial windows are enabled. Mean, median, energy, sign statistics, runs, and CUSUM are available from the first valid sample. `window_ready` remains false until `window_count == window_size`. Autocorrelation and skewness retain their separate minimum-sample and nonconstant-moment requirements. Warm-up rows are not full-window rows.

## Window statistics

For the most recent `n=min(W, consecutive_valid_count)` samples `x_1,...,x_n`, the mean is

```text
mu = (1/n) sum_i x_i.
```

The median is the usual ordered-sample median. An even-sized window uses the arithmetic mean of the two middle values.

Window energy is

```text
E = (1/n) sum_i x_i^2.
```

Energy is diagnostic only and cannot produce an alert in Day 9.

## Sign balance and runs

The sign is `+1` above `sign_zero_epsilon`, `-1` below its negative, and zero otherwise. Zero contributes to `zero_count`, contributes to neither positive nor negative count, and interrupts a same-sign run.

The dominant nonzero sign ratio is

```text
max(N_positive, N_negative) / (N_positive + N_negative).
```

It is NaN when every sample is zero. Current and maximum run lengths are computed only within the current bounded window and only across consecutive, nonzero, equal signs.

## Two-sided CUSUM

For fixed Quick reference `k=0.5`, each continuous valid segment uses

```text
C_positive(t) = max(0, C_positive(t-1) + x_t - k)
C_negative(t) = max(0, C_negative(t-1) - x_t - k).
```

The maximum is `max(C_positive, C_negative)`. The signed form is positive on a tie and otherwise takes the sign of the larger side. An invalid frame resets both internal states to zero.

Day 9 defines no CUSUM decision threshold `h`, no alert, and no binary classification.

## Lag-1 autocorrelation

Using the mean of the current window,

```text
rho_1 = sum_(i=2..n) ((x_i-mu)(x_(i-1)-mu))
        / sum_(i=1..n) (x_i-mu)^2.
```

It is valid only for `n>=3` and a denominator greater than `moment_epsilon`. A constant window returns NaN, not a fabricated zero or one.

## Population-moment skewness

Day 9 uses population moments without the Fisher-Pearson small-sample correction:

```text
m2 = (1/n) sum_i (x_i-mu)^2
m3 = (1/n) sum_i (x_i-mu)^3
skewness = m3 / m2^(3/2).
```

Skewness is valid only for `n>=3` and `m2 > moment_epsilon`. A constant window returns NaN.

## Raw and Huber isolation

Raw and Huber signals use separate `CausalInnovationWindow` instances. They do not share arrays, sign runs, CUSUM state, or initialization. A difference between their outputs never selects a method or changes the primary signal. Runtime and unit audits compare each stream against isolated processing.

## Output and schema

Quick writes

```text
results/stage2_failure_analysis/day9_quick/<run_id>/
  frame_window_statistics.csv
  day9_quick_summary.json
  run_manifest.json
```

The fixed schema is `stage2_failure_window_v1`. Every Day 8 online row has exactly one output row with the same frame key. Invalid-frame NaN values have explicit reset semantics; Inf is forbidden. Online output fields exclude ground-truth, oracle, scene, and offline error fields.

## Explicit exclusions and current status

Day 9 creates no anomaly threshold, alert, AUROC, FPR, F1, detection delay, best-statistic selection, representative Stage 2C replay, Reserved Test run, or scientific diagnostic figure. It does not establish that coherent bias is detectable.

Day 9 does not modify ODI, the translation Schur matrix, weak-direction extraction, eigengap reliability, Huber weighting, `huber_full`, Stage 2B, Stage 2C, trajectory, covariance, or experiment data. It implements no Stage 3 innovation detector or joint gate.

The project still has no FAST-LIO2 integration, real IMU propagation, or real data association. It remains a controlled synthetic research prototype, not a complete Degen-LIO system.

The only allowed status is

```text
DAY9_WINDOW_STATS_PASS = true/false
STAGE2_GATE = INCOMPLETE
STAGE3_GATE = NOT_STARTED
COHERENT_BIAS_DETECTABLE = UNDETERMINED
RISK_WARNING_AUTHORIZED = false
FAST_LIO2_INTEGRATION_AUTHORIZED = false
PUBLIC_DISCLOSURE_AUTHORIZED = false
```
