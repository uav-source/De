# Stage 2 Failure-Mechanism Diagnosis — Day 10

## Purpose and boundary

Day 10 is an engineering audit of one claim only: the existing Day 8 online
frame-diagnostic path and Day 9 causal window path do not depend on offline
ground truth. It adds no estimator, signal formula, threshold, alert, or
scientific experiment. `STAGE2_GATE` remains `INCOMPLETE`; no Stage 3 work is
started.

The online boundary contains `run_map_lio`, `Stage2FailureOnlineLogger`, the
Day 9 window statistics and schema, and the Day 9 orchestration. Their inputs
are estimator state, residuals, Jacobians, observation variance, robust
weights, detector outputs, update deltas, frame time, method, and seed
provenance. `pose_gt`, `axis_per_frame`, oracle directions, and error metrics
are offline-only.

Day 8 orchestration may evaluate GT after estimation because it writes two
separate products: an online CSV and an offline GT CSV. The GT evaluator is a
one-way consumer of completed online records and completed trajectories. It
must never feed values, decisions, directions, or state back into the
estimator or online logger. Day 10 deliberately calls the estimator and logger
directly instead of calling the complete Day 8 orchestration.

## Static and runtime audits

The static audit parses the five online modules with Python `ast`. It rejects
offline evaluator imports, forbidden GT parameters in selected public APIs,
AST parse failures, and GT/oracle tokens in the online and window schemas. A
legal offline evaluator is not removed or treated as an online dependency.

Every runtime check reuses the single deterministic `build_day8_unit_fixture`
result, motion, configurations, methods, thresholds, initial state, and seeds.
Nothing is resampled, and variant names never enter a seed. The five variants
are:

1. `gt_present_control`: the unchanged fixture;
2. `gt_removed`: both offline fields are absent;
3. `gt_access_sentinel`: offline fields are hidden and guarded;
4. `gt_poisoned`: offline arrays retain shape but contain fixed impossible
   values;
5. `gt_permuted`: offline arrays are reversed along time.

`GTAccessSentinelMapping` is read-only. Normal iteration, `items`, `values`,
and mapping copies expose only online fields. Direct indexing, `get`, or a
membership request for `pose_gt` or `axis_per_frame` records the attempt and
raises `ForbiddenGTAccessError`. A caught access is not converted into a pass.

## Equivalence contract

Continuous estimator arrays must have the same dtype and shape, contain only
finite values, differ by at most `1e-12`, and have an identical SHA-256 over
dtype, shape, and C-contiguous raw bytes. The audited arrays are prior poses,
posterior poses, applied deltas, full deltas, and covariances. Detector,
direction-stability, actionable-direction, and solver-failure flags must be
exactly equal.

Online records are compared field by field with the fixed schema order. Their
canonical hash encodes scalar types and finite floats exactly, represents NaN
explicitly, and distinguishes NaN, zero, and missing or extra fields. It
contains no path or creation time.

Each variant's online records are independently passed to the unchanged Day 9
window implementation with the frozen Day 9 Quick configuration. Frame keys,
raw and Huber statistics, CUSUM, sign runs, autocorrelation, skewness, rows,
and canonical record hashes must all match the control.

## File-system isolation

The no-GT sandbox contains only the Day 8 online CSV, its source manifest, and
the frozen Day 9 configuration as inputs. Day 9 runs in a separate clean
runner and must pass without a GT CSV. A second sandbox adds an intentionally
invalid `frame_diagnostics_gt.csv`; the produced window CSV must remain
byte-identical. Therefore the GT file is neither required nor consulted.

## Invalid reset end to end

The engineering fixture has 11 online rows: five valid, one invalid, then five
valid. It is written with the exact Day 8 online schema and passed through the
complete Day 9 file workflow. Expected window counts are
`1,2,3,4,5,0,1,2,3,4,5`. The invalid row has reason
`invalid_direction`, clears all state, and exposes NaN window statistics. The
next row starts a new negative window with raw mean `-1`, Huber mean `-0.8`,
raw positive CUSUM `0`, and raw negative CUSUM `0.5`. This is an engineering
reset check, not a scientific sample.

## Explicit non-claims

Day 10 creates no anomaly or detection threshold and computes no AUROC, FPR,
F1, recall, or detection delay. It does not replay a representative Stage 2C
seed or run Development, Test, or Reserved Test. Finding no dependency in the
audited path does not establish coherent-bias separability or H2.

There is still no Stage 3, no innovation gate, no bias-state estimator, and no
FAST-LIO2 integration. The prototype still lacks real IMU propagation and real
data association. It is not a complete Degen-LIO system.
