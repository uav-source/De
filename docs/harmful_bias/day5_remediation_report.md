# Day 5 Remediation V1 report

## Outcome

`DAY5_REMEDIATION_PASS=false`, `DAY5_RUNTIME_EQUIVALENCE_PASS=false`, and `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`.

Phase A completed all six planned pure `AUDIT_ONLY` replays and failed the strict baseline repeatability gate. The matrix stopped with `FAILURE_CLASSIFICATION=BASELINE_RUNTIME_NONDETERMINISM`; Phase B (`CAPTURE_ONLY`) and Phase C (`COMPACT_EXPORT`) were not executed.

This result cannot be attributed to the tap: the failing runs all had the tap and observation writer disabled.

## Failed V2 evidence retained

The previous failed V2 audit remains immutable at SHA-256 `58c2f0931705f52e9c467d0ece28223c65632694c3256dbbc979d97d0947baa9`, run-id `multihyp_day5_equivalence_v2`. Its fixed key evidence is 13,741 paired scans, 5 missing scans, maximum position difference 1.2146871969815247 m, maximum rotation difference 0.31414150667760504 rad, maximum covariance difference 1.0000003329214326, 3 final-map mismatches, mean overhead 129.78562569860483%/133.93899925239324%, and 22 V2 schema rejections.

The four remediation targets were: baseline instability, synchronous full JSON/neighbor/plane export overhead, fixed `1e-12` covariance symmetry rejection, and comparator `pass` overwrite.

## Engineering remediation

- Runtime modes are a single closed enum: `AUDIT_ONLY`, `CAPTURE_ONLY`, `COMPACT_EXPORT`.
- Day 3 `FULL_AUDIT_V1` remains unit-tested. Formal remediation uses `DETECTOR_MINIMAL_V1`.
- Minimal records contain scan identity/timestamps, prior pose, raw detector-order 6x6 covariance, N×6 detector Jacobian, formal innovation, scalar variance, counts, and formal checksums.
- Minimal records do not contain ordered neighbors, plane arrays, proxy-ID arrays, accepted-index arrays, or native 12-column Jacobian payload.
- Runtime audit is `HBRTAUD2`/version 2; observation export is `HBROBSV3`/version 3. Both use explicit little-endian serialization, payload length, per-record FNV-1a-64 checksum, and record-count/file-checksum trailer.
- Writers use an 8 MiB user-space buffer, no background thread, no per-frame flush, and shutdown flush/close.
- `MeasureGroup` checksum covers ordered LiDAR x/y/z/intensity/curvature plus ordered IMU sec/nsec, angular velocity, and linear acceleration, with counts and boundary timestamps.
- Tap pre/post checksums cover state, covariance, native Jacobian, innovation, geometric residual, formal correspondence, and map size. Export pre/post checksums cover estimator state/covariance/map digest.
- V3 preserves finite raw covariance and its checksum, records maximum asymmetry, and derives a detector-side symmetric copy as `0.5*(P+P.T)` without changing FAST-LIO2 covariance. Finite asymmetry alone is not a schema rejection.
- Every schema-valid observation produces one structured detector output, including detector-invalid records.
- Comparator results are independently named and quaternion comparison uses the locked stable `2*atan2` formula; raw state checksum mismatch still fails strict equivalence.

## Build and tests

- FAST-LIO2 `RelWithDebInfo` build: passed.
- FAST-LIO2 clean restore: 106 reported tests, failures 0, errors 0, skipped 0 (53 unique GoogleTest cases; `catkin_test_results` counts suite and case totals). The initial in-place workspace summary was 114 because it also counted a stale 4-case failed-V2 JSON-writer XML file; that writer and target are not present in the remediation source.
- Degen targeted pytest: 74 passed.
- Degen full pytest: 722 passed, 1 existing deprecation warning. The full run used three temporary read-only links to archived historical Day 11/12 checksum manifests; all links were removed after the run.
- Static audit: forbidden added FAST calls 0; writer estimator/map references 0; active JSON formatting hits 0; background threads 0; production detector/config/lock diff 0; forbidden IMU/ikd/config/launch diffs 0.

The audit-package restore was also executed with an isolated HOME and bundled wheels. It passed all 74 targeted Degen tests, the clean FAST build and 106-test report, binary round-trip fixture, comparator fixture, small-result hashes, and Gate fixture. Its full Degen run was honestly recorded as false: 623 passed, 85 failed, and 14 errored because the package intentionally omits the large gitignored historical Stage 2 result trees required by those tests. No rosbag replay was run during external restoration.

## Phase A evidence

All six replays exited successfully with the same binary SHA-256 `59deeb5302c3c575b04d6cb65b9decdd3e9042eb5d70447f5cc4ee4227d3c136`, locked bags, fixed CPU affinity, and valid runtime binary trailers/checksums.

`avia_quick_shack` was exactly repeatable across all three pairs: 490 paired scans per pair, zero missing scans, zero input/state/covariance/formal/map mismatches, and identical final maps.

For `avia_outdoor_run_100hz`, R1 and R2 were exactly identical with 6,382 records and an identical final map. R3 had 6,383 records and one extra leading input group:

- R1/R2 scan 0 begins at 126.55948725 s with 505 LiDAR points and 2 IMU messages.
- R3 scan 0 begins at 126.54950489 s with 298 LiDAR points and 4 IMU messages.
- R3 scan 1 has the same timestamps, counts, and `MeasureGroup` checksum as R1/R2 scan 0.

Therefore the first formal divergence is scan 0, stage `INPUT_GROUP`. R1-vs-R3 and R2-vs-R3 each have 6,382 paired indices, 1 missing index, 6,382 input-checksum mismatches, 6,381 posterior-state checksum mismatches, 6,376 posterior-covariance mismatches, 6,375 formal Jacobian/residual/correspondence mismatches, 6,376 map-size mismatches, and different final maps. Maximum observed differences are 6.311448361981912 m, 0.11773532575755596 rad, and 0.805910679062224 covariance units.

Outdoor R1/R2 final map: 41,430 points, checksum `2453831570008564932`. R3 final map: 41,672 points, checksum `4992726920699124107`.

## Phases B and C

Not executed because Phase A failed. Consequently:

- tap in-call immutability and export-call immutability are not evaluated by enabled-tap runs;
- capture/export overhead is not interpreted;
- V3 real replay schema acceptance, detector output completeness, and detector repeatability are not evaluated on real exported observations;
- tap/export mutation counters are numerically zero only because all executed runs were `AUDIT_ONLY`.

## Scientific boundary

`STAGE2_GATE=FAIL`, `TRANSITION=PIVOT`, `COHERENT_BIAS_HARMFUL_MECHANISM_SUPPORTED=true`, and `COHERENT_BIAS_STABLY_ONLINE_DETECTABLE=false` remain fixed. `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY5_REMEDIATION`.

This remediation did not evaluate harmful-bias detectability, did not implement multi-hypothesis estimation, IMU conflict, future validation, attenuation, or a new estimator, and did not complete formal Degen-LIO integration. Stage 3, Stage 4, Patent 2, FAST-LIO2 integration, risk warning, and public disclosure remain unauthorized.
