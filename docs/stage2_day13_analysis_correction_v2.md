# Stage 2 Day 13 Analysis Correction V2

## Scope

Day 13 V1 generated the preregistered calibration and evaluation trials correctly,
but its offline AUROC implementation selected every eligible clean frame in a
sweep. The design lock instead required one matched clean frame for each eligible,
stress-active `coherent_subhuber_slip` frame. The error is confined to negative
population selection; it is not an experiment-generation, seed, stress, estimator,
or logging error.

The V1 run and its locked analysis code remain byte-for-byte preserved. V2 is an
independent reader of the frozen V1 CSV files, because changing the V1 modules
would invalidate the analysis-code hash stored in `design_lock.json`. No trial is
rerun, no estimator is invoked, and V1 outputs are neither rewritten nor removed.

## One-to-one population

For each Geometry or Observation coherent active eligible frame, V2 requires one
unique eligible clean row with equal `sweep`, `level`, `geometry_seed`,
`sensor_seed`, `process_seed`, `method`, `frame_index`, and `timestamp`. Stress,
case ID, and stress provenance hashes are deliberately excluded from the key.
Missing rows, duplicate keys, or timestamp disagreement are errors. A nonfinite
statistic on either side invalidates the complete pair instead of retaining only
one side. Open Control, gross control, coherent inactive frames, and surplus clean
frames never enter the AUROC population.

The frozen primary population changes as follows:

| Sweep | V1 positive | V1 negative | V2 positive | V2 negative |
| --- | ---: | ---: | ---: | ---: |
| Geometry | 1600 | 2800 | 1600 | 1600 |
| Observation | 1600 | 2800 | 1600 | 1600 |

The corrected `huber_cusum_max` AUROCs are approximately 0.5993 for Geometry and
0.6862 for Observation, versus V1 values of approximately 0.5946 and 0.6726.
Both remain substantially below the preregistered 0.80 review target.

## Locked operating point and FPR populations

The statistic remains `huber_cusum_max`, and the calibration-locked threshold
remains `13.745952939169019` with strict comparison `score > threshold`. V2 does
not select a new statistic or retune the threshold. At roughly 8%–9% matched-clean
FPR, the threshold detects only about 14.6%–22.3% of coherent active frames. This
low TPR is reported directly rather than hidden behind the AUROC table.

`clean_all` combines `weak_clean` and `open_control`, which have materially
different false-positive rates. V2 therefore reports calibration and evaluation
FPR separately for all three populations. In evaluation, combined clean and Open
Control meet 10%, while weak clean is slightly above it. The correct status is
`MIXED_POPULATION_DEPENDENT`; the combined value cannot support a blanket claim
that every clean population passes.

## Gross-control interpretation

The existing V1 case summaries are retained and reported by level. Huber produces
the expected downweighting in most configurations, but Geometry L4 has median
downweighting zero and a zero-downweight case ratio of 0.625. Gross-control
behavior is therefore clearly level-dependent and cannot be summarized as
uniformly effective.

## Scientific boundary

The controlled coherent-slip mechanism increases harmful updates, but the locked
`huber_cusum_max` statistic does not provide adequate discrimination under the
preregistered new-seed evaluation.

After correcting the negative population to one-to-one matched clean frames,
AUROC remains substantially below 0.80 for both Geometry and Observation sweeps.

This correction authorizes Day 14 scientific review only. It does not authorize
Stage 3, FAST-LIO2 integration, or risk-warning claims. Day 14 is responsible for
the final Stage 2 scientific judgment. The current project has no real IMU, no
real data association, and no formal FAST-LIO2 integration; it is not a complete
Degen-LIO system.

