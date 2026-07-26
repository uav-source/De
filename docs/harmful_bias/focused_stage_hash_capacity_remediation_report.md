# Focused Stage-Hash Capacity Remediation Report

## Outcome

The bounded diagnostic collector remediation passed. The maximum inclusive
window was raised from 26 records to 51 records, the production binary was
built once, and all FAST and Degen tests passed. Four new Quick Shack runs
completed with 487 observation records, 51 focused stage records, and 102
coherent snapshots each.

The evidence-collection execution Gate passed, but the scientific localization
Gate did not. Five pairs showed formal differences and one pair was formally
identical. The focused records first differed at scan 157 or 162 in
`map_content_after`, while the full semantic stream first differed at scan 158
or 194. The frozen Gate requires those first-divergence scans to match, so the
result is `EVIDENCE_GAP`: `formal_branch_reproduced=false`,
`formal_branch_stage_localized=false`, `experiment_a_pass=false`, and
`day7_recommended=false`.

## Why the previous focused run had no sensor replay

The failed focused audit requested the inclusive 155–205 window, which contains
51 records. The frozen binary rejected it before bag unpause because
`configure()` had an explicit `requested > 26U` guard. Consequently it produced
zero LiDAR callbacks, zero IMU callbacks, zero observations, and zero stage
records. The failure was a bounded collector-capacity rejection, not a
scientific result.

The collector uses a vector with `reserve(capacity_)` and a
`records_.size() >= capacity_` guard; 26 was an explicit configuration limit,
not a fixed-array limit. This remediation changed that named maximum to 51
rather than removing the bound. A 52-record window remains rejected.

## Source and test scope

Only these FAST files changed:

- `include/experiment_a_stage_hash_audit.hpp`
- `src/experiment_a_stage_hash_audit.cpp`
- `test/test_experiment_a_stage_hash_audit.cpp`

The new constant is
`kExperimentAStageHashMaximumRecordCount = 51U`. The old 135–160 window still
accepts 26 records, 155–205 accepts 51 records, 155–206 is rejected, a 52nd
record is not stored, and disabled mode remains empty. Direct execution passed
41/41 gtests. The full FAST suite passed 268 tests with zero errors and zero
failures. Degen targeted tests passed 36/36 and the full suite passed 1133
tests with one skip.

No formal estimator mathematics, hash field order, snapshot logic, ikd-tree
logic, `laserMapping.cpp`, CMake, package metadata, or thread configuration was
changed. The production build count was exactly one. The old binary SHA was
`3dff4043d7450c0454c1cecedc0baf092e2cc8c47fecab10fd2fe014d0b00250`;
the new binary SHA is
`907566d1e99f2f8aae1e7935205e723a78dfab1ceb0a391905c62ec2255f6d78`.

Three run-lock candidates were rejected before any roscore, FAST process, bag
process, callback, or scientific runtime product. Their failures were lock
schema validation issues only. They consumed zero sensor replays. The accepted
lock passed static transport-field, source, binary, and clip preflight before
the four real runs.

## Four-run completeness

| Run | Port | Wrapper/raw | LiDAR/IMU | Observation SHA | Stage | Snapshots |
| --- | ---: | --- | --- | --- | --- | --- |
| r1 | 20311 | 0/30, adjudicated | 491/9953 | `926fcb842be12939104e7fe1041f8eeef4c1aa2d9c78d7acf2f3063eec2d95cf` | 51, 155–205 | 102 coherent |
| r2 | 20312 | 0/30, adjudicated | 491/9953 | `7295e14c8a9ade76c5d844a547971f61a4b9eff82341f701f0673b835e1cfb76` | 51, 155–205 | 102 coherent |
| r3 | 20313 | 0/30, adjudicated | 491/9953 | `b4c792d9e96d6f93c8e8723004d33301c06b07412d52fb2217afeecbb94bfdad` | 51, 155–205 | 102 coherent |
| r4 | 20314 | 0/30, adjudicated | 491/9953 | `a9b91080f6519e3b41d0b960753248fc598f6cfec818a94a702a6ee4e8494903` | 51, 155–205 | 102 coherent |

Every run had 490 runtime scans and 487 observations. Incoherent snapshots,
cross-scan violations, tap drops, writer errors, binary errors, truncations,
extra bytes, in-call mutations, diagnostic mutations, schema rejections, and
GT consumption were all zero. Drain, normal shutdown, runtime-product
validation, and the frozen tail adjudication passed.

## Six-pair result

| Pair | Semantic mismatches | Full first record/scan | Focused first scan/stage | Classification |
| --- | ---: | --- | --- | --- |
| r1-r2 | 332 | 155/158 | 157/`map_content_after` | `MAP_INSERTION_STAGE_DIVERGED` |
| r1-r3 | 0 | none | none | `NO_FORMAL_DIVERGENCE` |
| r1-r4 | 296 | 191/194 | 162/`map_content_after` | `MAP_INSERTION_STAGE_DIVERGED` |
| r2-r3 | 332 | 155/158 | 157/`map_content_after` | `MAP_INSERTION_STAGE_DIVERGED` |
| r2-r4 | 332 | 155/158 | 157/`map_content_after` | `MAP_INSERTION_STAGE_DIVERGED` |
| r3-r4 | 296 | 191/194 | 162/`map_content_after` | `MAP_INSERTION_STAGE_DIVERGED` |

Previous-scan identity passed for all six pairs. There were three unique formal
trajectory clusters: `{r1,r3}`, `{r2}`, and `{r4}`. Raw LiDAR and IMU hashes
matched across all pairs. Differences were observed in later undistorted,
map-content, correspondence/J/h/residual, post-update, insertion, and
map-content-after fields for the five divergent pairs. The r1-r3 pair differed
only in traversal-related diagnostic fields and was not counted as a formal
branch.

## Isolated restore

The final audit directory was restored and verified with a temporary HOME,
user-site Python disabled, and no ROS, bag, or detector execution. The restored
FAST source built successfully, all 268 FAST tests passed, the 26/51/52 capacity
checks passed, all four binaries and 204 stage records parsed, all 408 snapshots
were coherent, and all six semantic/stage comparisons plus clustering were
recomputed byte-for-byte. The focused Degen suite passed 36/36.

The optional external full Degen suite was attempted and reported `false`
because the bounded package deliberately does not vendor the unrelated
`jsonschema` dependency; collection stopped with 26 missing-module errors.
This does not change the successful targeted restore or the primary-workspace
full-suite result of 1133 passed and one skipped.

## Authority boundary

`FOCUSED_STAGE_HASH_CAPACITY_REMEDIATION_PASS=true` and
`FOCUSED_STAGE_155_205_REPLAY_AUTHORIZED=true` describe this bounded
remediation and its completed four-run matrix only. No fifth replay was run.
The production detector, ODI, AIS, weak-direction computation, detector
feedback, and GT were not used.

`STAGE2_GATE=FAIL`, `TRANSITION=PIVOT`,
`CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`,
`DAY7_AUTHORIZED=false`, `STAGE3_START_AUTHORIZED=false`, and
`FAST_LIO2_INTEGRATION_AUTHORIZED=false` remain fixed. Day 7 still requires a
separate GPT audit and explicit authorization.
