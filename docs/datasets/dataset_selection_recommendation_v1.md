# Dataset Selection Recommendation v1

- Audit label date: 2026-07-25
- Execution date: 2026-07-15
- No data was downloaded. The priorities below authorize no download by themselves.

## Priority A — first small format probes

### 1. MUN-FRL

- Suggested sequences: `lighthouse` benchmarking bag first; then `quarry1`; only later `bell412_dataset1`.
- Role: first adapter feasibility probe and principal UAV generalization source.
- Why: the official release provides hardware synchronization, calibration, synchronized bags, PPK position/6DoF references, a CC BY 4.0 data license, and published FAST-LIO2 launch/evaluation material.
- Largest defect: the exact PointCloud2 fields still need inspection; Bell412 structureless runs are documented FAST-LIO2 failure cases and are not suitable for the first adapter test.
- FAST-LIO2 effort: `MINOR_ADAPTER`—topic mapping, frame direction, time field and unit assertions.
- GT supports: position RMSE/ATE, 6DoF trajectory comparison, drift and time-aligned detection analysis.
- GT does not automatically support: independent orientation truth free of PPK-aided estimation assumptions; indoor GNSS-denied accuracy claims.
- Minimum later download: the official `Lighthouse_benchmarking_bag`, 3.55 GB.

### 2. SubT-MRS

- Suggested sequences: `Long_Corridor`, `Multi_Floor`, then `BlockLiDAR` as a failure case.
- Role: principal tunnel/underground degeneration source.
- Why: it directly covers underground long corridors, caves, multi-floor environments and sensor obscurants on multiple robot types.
- Largest defect: no explicit data license was found in the audited official pages, and sensor models/point schemas are sequence-dependent.
- FAST-LIO2 effort: `MAJOR_ADAPTER`—select a LiDAR+IMU sequence, inspect the bag, normalize PointCloud2 or reconstruct from packets/LAS, verify time units and extrinsics.
- GT supports: ATE/RPE only on sequences whose full reference and coordinate definition are verified.
- GT cannot support: a blanket accuracy claim across all SubT-MRS scenes; some modality-degradation sequences do not contain LiDAR.
- Minimum later action: request written license clarification before any data download; then obtain only the `Long_Corridor` package.

### 3. Hilti SLAM Challenge Dataset 2021

- Suggested sequences: `Basement` as the 6 GB format probe; then `Construction Site Outdoor 1`; keep Basement 1/3/4 as one location group.
- Role: secondary construction/basement difficult source.
- Why: official ROS bags contain calibrated Ouster/Livox and IMU data, TF, sub-millisecond alignment, and real construction/featureless environments.
- Largest defect: most sequences provide sparse 3DoF stationary control points rather than continuous full-trajectory GT.
- FAST-LIO2 effort: `MAJOR_ADAPTER` pending PointCloud2/CustomMsg field inspection and exact IMU selection.
- GT supports: checkpoint translation error and sparse consistency; full 6DoF metrics only for the explicitly 6DoF sequences.
- GT cannot support: full-coverage ATE for Basement and construction sequences with only 3DoF checkpoints.
- Minimum later download: `Basement` (6 GB), not all 181 GB.

### 4. Newer College Multi-Camera LiDAR-Inertial Extension

- Suggested sequences: `Stairs` and `Cloister` for geometry stress; keep the entire Maths family evaluation-only, with `Maths-Easy` as open control.
- Role: principal handheld open-control and paired-difficulty source.
- Why: hardware synchronization, nine named sequences, narrow/repetitive and open scenes, and centimetre-accurate 6DoF GT at 10 Hz.
- Largest defect: the official page does not enumerate processed PointCloud2 time/ring fields; a raw packet or processed-cloud probe is required.
- FAST-LIO2 effort: `MAJOR_ADAPTER` until the point schema is confirmed; likely reduced after a successful Ouster probe.
- GT supports: full ATE/RPE and trajectory-aligned ODI/weak-direction analysis.
- GT cannot support: an independent environment split if closely related New College or Maths repeats are divided across tuning and test.
- Minimum later download: one `Stairs` bag plus its calibration and GT, if the request form permits sequence-level selection.

### 5. NTU VIRAL

- Suggested sequences: `tnp_01`/`tnp_03` as one indoor-development group; `eee_01` as independent UAV open control.
- Role: secondary UAV generalization and aerial indoor/outdoor contrast.
- Why: explicit Ouster PointCloud2 `t` and `ring` fields, high-rate raw IMU, calibration, 18 downloadable bags and laser-tracker position reference.
- Largest defect: the official site documents Ouster cloud/IMU timestamp jitter, and the laser tracker provides position but no orientation ground truth.
- FAST-LIO2 effort: `MINOR_ADAPTER` after applying the official regularization script and verifying deterministic output.
- GT supports: position ATE/RMSE and detection timing after applying the 0.4 m IMU-to-prism offset.
- GT cannot support: direct orientation error against independent ground truth.
- Minimum later download: `rtp_03` (4.0 GB) for the smallest official bag, or `tnp_03` (5.5 GB) if indoor geometry is mandatory.

## Priority B — add after the principal adapter works

### M2DGR

Use `room_01` (14.0 GB) as the smallest full-GT probe, `hall_02` for indoor structure, and `street_02` only as a later open control. It has excellent GT breadth but a 1.22 TB total size, unstable OneDrive access, and an undocumented per-point timing schema. Adapter: `MAJOR_ADAPTER`.

### TIERS Enhanced

Use `Indoor09` and `Indoor10` together as a validation family and `Road3` as open control. The multi-LiDAR data are valuable for sensor generalization, but indoor SLAM+ICP ground truth is not an independent external reference. Adapter: `MAJOR_ADAPTER`.

### Newer College Original

Use `short_experiment`/`long_experiment` as an evaluation-only normal group. It supplies strong full-trajectory control data, but is software synchronized and needs the same Ouster field probe. Adapter: `MAJOR_ADAPTER` pending inspection.

## Priority C — sensor/generalization or backup only

### MulRan

Use `DCC01` or `KAIST01` only after deterministic file-to-bag conversion is established. The 0.6 GB ParkingLot sample is LiDAR-only and is not an LIO feasibility sample. Adapter: `MAJOR_ADAPTER`.

### HeLiPR

First inspect the one-minute `Roundabout01` sample and confirm that the requested package includes IMU, GT and all needed stamps. Use the main sequences only for heterogeneous LiDAR generalization; their asynchronous sensor files and size make this a major adapter task. Adapter: `MAJOR_ADAPTER`.

## Rejected

No named candidate is hard-rejected at source-audit level. SubT-MRS is `LIMITED_USE` until its license is clarified; this is a blocking hold, not an invented rejection. Individual sequences lacking IMU, full GT, or deterministic timestamps remain excluded from accuracy evaluation.

## Recommended acquisition order

1. MUN-FRL `Lighthouse_benchmarking_bag` (3.55 GB).
2. NTU VIRAL `rtp_03` or `tnp_03` after choosing open versus indoor priority.
3. Hilti `Basement` (6 GB).
4. One Newer College Extension sequence plus calibration/GT.
5. SubT-MRS `Long_Corridor` only after license clarification.
