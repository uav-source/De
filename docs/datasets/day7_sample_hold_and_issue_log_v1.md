# Stage 1 Day 7 Sample Hold and Issue Log v1

## Counts

- `P0_ISSUE_COUNT=0`
- `P1_ISSUE_COUNT=8`
- `P2_ISSUE_COUNT=3`

No unresolved coordinate, point-time-unit, IMU-unit, sensor-selection, corruption, or extrinsic-direction error is permitted in either READY input specification. NTU's archive calibration resolved the apparent linked-config ambiguity before release.

## P1 — actionable warnings and holds

| ID | Dataset | Finding | Disposition |
|---|---|---|---|
| D7-P1-01 | MUN-FRL | Bag-record timestamps use a 2025 epoch while raw sensor headers use a 2022 epoch. Both are monotonic, but they must not be mixed. | Adapter input contract requires message headers. |
| D7-P1-02 | MUN-FRL | The workshop bag contains raw `/fix` RTK position but omits documented `/fix_ppk` and `/fix_frl`; it has no independent attitude GT. | Restrict reference use to `POSITION_ONLY`. |
| D7-P1-03 | MUN-FRL | IMU median inter-arrival frequency is 733.270 Hz while interval-span average is 399.882 Hz; 715 positive gaps exceed five median intervals. | Preserve headers and add cadence diagnostics; do not rescale time. |
| D7-P1-04 | NTU VIRAL | The publisher documents Ouster/IMU synchronization jitter; the linked FAST-LIO setup prescribes `-0.1 s`. | READY is MAJOR and requires the official regularization/timing branch before algorithm use. |
| D7-P1-05 | NTU VIRAL | The official-site-linked FAST-LIO config says 32 scan lines and contains 12 `extrinsic_R` values, conflicting with the 16-line sensor and 3x3 requirement. | Checksum-verified archive YAML resolves 16 lines, `R=I`, and transform direction; Day 8 must reject the malformed form. |
| D7-P1-06 | Newer College Extension | Official Stairs file returned a high-demand Google Drive quota error. | `BLOCKED_DOWNLOAD`; no actual-field claim. |
| D7-P1-07 | Hilti 2021 | Basement minimum is approximately 6 GB, over the 4 GiB Day 7 source cap. | `NOT_SELECTED`; no download. |
| D7-P1-08 | SubT-MRS | No explicit dataset license/use permission was established on the audited official source. | `HOLD_LICENSE`; no download. |

## P2 — noncritical engineering/documentation items

| ID | Dataset | Finding | Disposition |
|---|---|---|---|
| D7-P2-01 | NTU VIRAL | A 6,946,816-byte `rtp_03` transfer was stopped for poor throughput before switching to bounded `eee_03`. | Private partial retained as evidence; never counted as a valid sample. |
| D7-P2-02 | NTU VIRAL | Older page metadata differs from the actual archive in advertised size and calls the point field `noise`; the actual bag uses `ambient`. | Manifest and adapter contract use exact official object metadata and inspected fields. |
| D7-P2-03 | Both replays | Two runs had identical per-topic counts/ranges/frames but different asynchronous callback interleaving hashes. | Short replay passes; retain hashes as scheduling diagnostics, not data-order failures. |

## P0 prevention evidence

- Both downloaded payloads match resolved sizes; NTU also matches its official MD5 and passes ZIP CRC/path-safety checks.
- Three head/middle/tail scans per sample establish point field layouts and point-time ranges.
- MUN `time` is seconds; NTU `t` is nanoseconds.
- IMU messages use SI units and the chosen NTU IMU is the VN100 body IMU.
- MUN official-linked FAST-LIO semantics and NTU archive matrices explicitly place the LiDAR pose in IMU/Body; neither READY adapter requires inversion.
- GT limitations are explicit and neither sample is released for 6DoF ATE/RPE.
