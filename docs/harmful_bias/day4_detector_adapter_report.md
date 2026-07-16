# Harmful-Bias Multihyp Research Spike — Day 4 Report

## Outcome

Day 4 implemented one narrow integration: map a Day 3 read-only FAST-LIO2
observation record into the existing production degeneration detector and prove
that the adapter result is exactly equivalent to a direct production call on
three deterministic synthetic records.

```text
DAY4_SYNTHETIC_DETECTOR_ADAPTER_PASS=true
DAY5_RUNTIME_EQUIVALENCE_AUTHORIZED=true
OFF_ON_REPLAY_EQUIVALENCE_STATUS=NOT_RUN_DAY4
HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY4
```

Day 5 authorization permits only a later Quick-bag detector OFF/ON runtime
equivalence audit. It does not authorize Stage 3, estimator changes,
multi-hypothesis logic, a harmful-bias detectability claim, or complete
Degen-LIO integration.

## Frozen Day 3 boundary

Day 3 was retested before being frozen. FAST-LIO2 passed its RelWithDebInfo
build and 34 gtests; Degen-LIO passed 41 targeted and 631 full tests. The frozen
commits are:

- Degen-LIO `e9e18df9e5ee063549b77f419a46a6128b61516c`, tagged
  `checkpoint/multihyp-d3-pass`;
- FAST-LIO2 `f19b4c42a77dc11793c912d67b9e56dcafa279dc`, tagged
  `checkpoint/fastlio2-readonly-tap-v1-pass`.

FAST-LIO2 remained clean and unchanged throughout Day 4. No Day 4 commit was
created.

## Production detector resolution

The Day 2 source map, adapter contract, and frozen Stage 2A artifact identify a
single production per-frame entrypoint:

```text
src/degen_detector/odi_tracker.py::compute_metrics_for_frame
source SHA-256 c515e5321e569ed074ae1c4f33563e73a82775800f20197612c2816086676d17
candidate count 1
ambiguity count 0
metric version detector_stage2a_v1
```

The adapter uses `configs/detector/odi_stage2a.yaml` and the locked
`artifacts/current/detector_stage2a/locked/detector_lock.json`. Their SHA-256
values are respectively
`665c3df8f794841ac5f3afe97e77f9993aaae2feaf3510043ecff6646acf2398`
and `075f14217f5e9c782bc1ab4051e6533f34d4932399c7f4b8cbc60a03d62fe358`.

## Thin adapter mapping

The adapter first invokes the Day 3 formal observation validator. It copies the
already mapped `detector_pose_jacobian_rows` directly as `N x 6` float64 data;
there is no second column reorder. The state order is rotation then WORLD-frame
translation. It selects `formal_filter_innovation_h`, verifies the Day 3
`h=-pd2` contract, and expands the caller-owned scalar variance with `np.full`.
It does not invert or square-root variance and does not introduce per-point
confidence.

The production entrypoint does not consume prior covariance, so the adapter
does not include it in detector inputs. The adapter contains no ODI, AIS,
information-matrix, Schur, spectral, condition-number, weak-direction,
eigengap, Huber, or threshold formula. It calls production and maps production
outputs to the Day 4 schema. The production canonical direction is returned
unchanged.

## Output schema and invalid handling

The output schema records provenance, three canonical SHA-256 checksums,
translation metrics and spectrum, weak direction in WORLD, and trigger/action
booleans. It is explicitly synthetic-only and contains no GT, later-frame,
evaluation-partition, harmful-score, candidate, IMU-conflict, or future-gain
field.

The Python validator checks required fields, finite valid values, ascending
three-element spectra, unit direction, boolean implications, closed invalid
reasons, forbidden fields, and output payload checksum. It does not recompute
detector results. A schema-valid five-row record returns a structured invalid
output with `TOO_FEW_CORRESPONDENCES`; no rows are fabricated.

## Deterministic synthetic integration

The fixed fixtures are:

- `well_conditioned`: 36 rows and balanced translation information;
- `weak_x`: 24 rows, synthetic direction alignment `1.0` with WORLD x;
- `weak_rotated`: 24 rows, synthetic direction alignment `1.0` with
  `[1,1,0]/sqrt(2)`.

All three adapter calls are valid. For every required scalar, spectrum,
direction, and boolean field, adapter versus direct-production maximum absolute
error is `0.0`. Each input remains deeply equal with the same canonical input
SHA-256. Each fixture produces the same canonical output SHA-256 on three
consecutive calls. All three outputs pass both the Python validator and the
JSON schema.

The weak-axis expectations exist only in tests and are not output fields. The
fixtures use no random numbers, real records, bags, GT files, Development,
Holdout, or Future Test information. These results demonstrate integration
equivalence only; they are not scientific detectability evidence.

## Tests and static audits

- Day 4 targeted pytest: 77 passed;
- Degen-LIO full pytest: 667 passed, one pre-existing deprecation warning;
- production direct equivalence: 3/3;
- input immutability: 3/3;
- three-call determinism: 3/3;
- schema validation: 3/3;
- detector artifact ordered tree digest before/after:
  `4b34576a1acb49d50ccceb54dc76c3aa86ea41c80bbb238e11d18f1c209352de`;
- forbidden adapter mathematics matches: 0;
- forbidden adapter data dependencies matches: 0;
- FAST-LIO2 Day 4 status entries: 0;
- production detector/config/artifact diff entries: 0;
- unexpected Day 4 diff paths: 0.

## Actions not performed

Day 4 did not run roscore, roslaunch, rosbag, Quick, Development, Holdout, or
Future Test. It used no real data and ran no scientific experiment. It did not
modify FAST-LIO2, production detector source, detector artifacts, config, lock,
threshold, state, covariance, gain, map, correspondence, or filter update. It
did not implement multi-hypothesis logic, IMU conflict, held-out validation, or
future-frame validation. No Day 4 commit was created and nothing was pushed.

## Isolated restoration and bundle-size boundary

The audit restoration was exercised in a temporary HOME from the packaged
Degen baseline bundle plus the uncommitted Day 4 overlay. A curated 70 MB
historical test overlay was extracted from the fixed Day 14 V3 archive
(`99ada237ea91e943c227d36324e77b853ceccde7c06e18d99fb42a4a275735e1`);
the complete V3 package, wheels, and unrelated results are not included. The
isolated results are 77 targeted tests passed, 667 full tests passed, and 3/3
synthetic pipeline records passed with all output hashes verified.

The exact FAST-LIO2 frozen Git bundle was generated, verified, and separately
cloned successfully at HEAD `f19b4c42a77dc11793c912d67b9e56dcafa279dc`.
Its SHA-256 is
`eca5a3a584da43b804b4c12d2871c564c50a31ac76663281293e865b9c298d85`,
but its size is 132,967,641 bytes, already larger than the complete audit
package's 120 MiB limit. It is therefore not embedded. The package contains a
34,268-byte hash-pinned snapshot of the five frozen Day 3 FAST-LIO2 files,
their exact patch/tree identities, and the external clone evidence. Snapshot
SHA-256 is
`588e8dcaf0e15185982054d5719464cca21782b2af2ee4973a65a28bfb65ba7d`.
This size-driven substitution is explicit in the manifest and restore output;
it is not represented as an in-package exact Git clone.

The fixed scientific state remains:

```text
STAGE2_GATE=FAIL
TRANSITION=PIVOT
COHERENT_BIAS_HARMFUL_MECHANISM_SUPPORTED=true
COHERENT_BIAS_STABLY_ONLINE_DETECTABLE=false
STAGE3_START_AUTHORIZED=false
STAGE4_START_AUTHORIZED=false
PATENT2_AUTHORIZED=false
FAST_LIO2_INTEGRATION_AUTHORIZED=false
RISK_WARNING_AUTHORIZED=false
PUBLIC_DISCLOSURE_AUTHORIZED=false
```

Only the synthetic side-path detector adapter is complete. OFF/ON rosbag
equivalence and harmful-bias detectability remain unevaluated, and formal
Degen-LIO remains incomplete.
