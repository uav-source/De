# Day 5 real FAST-LIO2 runtime read-only equivalence report

## Answer

`DAY5_RUNTIME_EQUIVALENCE_PASS=false` and
`OFF_ON_REPLAY_EQUIVALENCE_STATUS=FAIL`. The locked v2 run completed all eight
planned Quick replays with one binary, but did not demonstrate bitwise or
1e-12 numerical equivalence. `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`.

This is an engineering failure result, not evidence about harmful-bias
detectability. `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY5`.

## Execution record

Day 4 was committed as `711ac05ccc683263446fb8656c0054048832f54c` and tagged
`checkpoint/multihyp-d4-pass`. FAST-LIO2 remained based on Day 3 commit
`f19b4c42a77dc11793c912d67b9e56dcafa279dc`. The final binary SHA-256 was
`a73352004465eaa9ab93eb2cf9007dc00039171473cc018f17f9f56e9ac6245b`
before and after every v2 run.

An initial `multihyp_day5_equivalence_v1` OFF_R1 attempt used a relative output
root and then encountered the pre-existing stopped-sim-time shutdown behavior.
It was marked `FAILED_ABORTED_NOT_REUSED`; no result from it was reused. The
runner was limited to absolute output normalization and SIGINT followed by ROS
shutdown to wake `ros::Rate::sleep`, then re-tested and locked under the new
run-id `multihyp_day5_equivalence_v2`. No estimator, audit, writer, detector,
comparison, tolerance, or threshold code changed after the v2 lock.

The v2 matrix completed 8/8 runs in fixed ABBA order for
`avia_quick_shack` and `avia_outdoor_run_100hz`. Each run had a fresh ROS
master/home/log directory. Bag hashes, source hashes, binary hash, and the
non-allowlisted parameter comparison all passed. No Development, Holdout-Dev,
or Future Test was run.

## Runtime equivalence results

The four primary OFF/ON comparisons paired 13,741 scans and had 5 missing
scans, all in outdoor OFF_R1 versus ON_R1. Duplicate scan count was zero. The
maximum differences were:

- position: 1.2146871969815247 m;
- quaternion geodesic rotation: 0.31414150667760504 rad;
- covariance absolute element: 1.0000003329214326.

Aggregated primary-pair checksum mismatches were 14,242 state, 14,232
covariance, 14,228 Jacobian, 13,848 residual, 6,372 accepted-index, and 6,926
formal-correspondence mismatches. Per-scan map size mismatched 6,372 times.
Three of four primary final-map checksum comparisons failed.

Shack exhibited two alternating outcomes: OFF_R1 matched ON_R2, while ON_R1
matched OFF_R2. Outdoor similarly had OFF_R1/ON_R2/OFF_R2 aligned while ON_R1
had five fewer scans and a different state/map outcome. Because differences
also occur within mode, this matrix does not support attributing them solely to
the tap. The hard contract nevertheless requires every paired checksum and
repeat to agree, so the equivalence gates fail.

The generated `equivalence_summary.csv` has a known presentation limitation:
its generic `pass` column was overwritten by the final-map subcomparison when
the locked comparator merged fields. Gate computation did not use that column;
it used explicit pose/covariance/checksum/map fields. The locked comparator was
not changed after observing results.

## Record and detector pipeline

ON generated 13,704 real v2 records. Tap drops, lifecycle drops, writer errors,
and nonfinite counts were all zero. Shack had 486 observations in each ON run,
exactly matching first-valid counts. Outdoor had 6,364 and 6,368 observations.

The strict runtime validator rejected 14 early outdoor ON_R1 records and 8
early outdoor ON_R2 records because their 6×6 prior covariance blocks exceeded
the frozen 1e-12 symmetry contract. These 22 records were retained in invalid
record logs; the validator was not relaxed. The remaining 13,682 records
produced 13,682 detector outputs. Seventeen detector outputs were explicit
invalid results. Each ON input was processed twice and all four repeated output
file checksums matched.

Detector execution was exclusively
`POST_REPLAY_READONLY_PRODUCTION_DETECTOR`. It read no bag, GT, label, holdout,
or future data and did not feed back to FAST-LIO2. Aggregate weighted detector
runtime mean was approximately 8.302 ms per output; the maximum per-run q95 was
27.894 ms. ODI ranges and counts are retained only as descriptive runtime
summaries; no AUROC, AUPRC, FPR, Recall, harmful rate, or sequence-superiority
claim was computed.

## Runtime overhead

After skipping the first 20 valid updates per pair:

- shack: mean 129.786%, median 97.319%, q95 286.858%; tap capture mean/q95
  0.214/0.459 ms and serialization mean/q95 1.981/4.574 ms;
- outdoor: mean 133.939%, median 114.138%, q95 325.544%; tap capture mean/q95
  0.098/0.179 ms and serialization mean/q95 0.986/2.120 ms.

Both the hard limits (mean 25%, q95 40%) and target limits (mean 10%, q95
15%) failed independently for both sequences.

## Safety and scope

Source lock, same binary, parameter allowlist, bag hash, replay completeness,
no-nonfinite, no-GT, and Day 5 diff-scope gates passed. Runtime symmetry,
pairing, pose, covariance, map size, final map, correspondence, residual,
Jacobian, accepted-index, record-schema/completeness, and runtime overhead hard
gates failed.

No production detector math/config/lock/threshold, formal measurement variance,
filter, map algorithm, correspondence selection, point filter, iteration count,
or OpenMP setting was changed. No multihypothesis, IMU conflict, map requery,
future validation, Day 5 commit, or push was performed.

The fixed scientific state remains `STAGE2_GATE=FAIL`, `TRANSITION=PIVOT`, all
Stage 3/4, patent, integration, risk-warning, and public-disclosure
authorizations false. The formal Degen-LIO system is not complete.

## External restore result

The packaged isolated restore passed the 62-test Degen Day 4+5 target, rebuilt
FAST-LIO2 from the Day 3 archive plus Day 5 overlay, passed all 84 FAST tests,
verified the synthetic comparator fixture, and verified package hashes. It did
not run rosbag. External Degen full pytest is explicitly `false`: the local
full suite requires approximately 46 MiB compressed gitignored Day 8/9/11–13
historical result evidence, which was excluded to keep the audit package under
the mandatory 150 MiB limit. The in-workspace full suite had already passed
693 tests before the v2 replay lock.
