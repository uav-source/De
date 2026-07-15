# Degen-LIO Public Dataset Feasibility Matrix v1

- Audit label date: 2026-07-25
- Execution/source-check date: 2026-07-15
- Scope: source audit and selection only; no dataset was downloaded and no experiment was run.
- Evidence rule: only an official dataset site, official repository, formal dataset paper, or official documentation was accepted as evidence.

The machine-readable matrix is `dataset_feasibility_matrix_v1.csv`. Unknown fields remain `UNKNOWN`, `PARTIAL`, or are explained in notes; a ROS bag by itself is not evidence of direct FAST-LIO2 compatibility.

## Decision summary

| Dataset | Score / 24 | Feasibility | Proposed role | FAST-LIO2 | Principal strength | Controlling limitation |
|---|---:|---|---|---|---|---|
| MUN-FRL | 23 | VERIFIED_USABLE | UAV_GENERALIZATION | MINOR_ADAPTER | Hardware sync, calibration, PPK reference, official FAST-LIO2 launch/evaluation | PointCloud2 field-level probe still required; Bell412 has published structureless failures |
| Newer College Multi-Camera Extension | 22 | USABLE_WITH_ADAPTER | OPEN_CONTROL | MAJOR_ADAPTER | Hardware-synchronized paired normal/challenging handheld sequences and 10 Hz 6DoF GT | Processed PointCloud2 point timing/ring schema not explicitly documented |
| NTU VIRAL | 21 | USABLE_WITH_ADAPTER | UAV_GENERALIZATION | MINOR_ADAPTER | Officially documented per-point `t`/`ring`, aerial indoor/outdoor sequences | Ouster/IMU jitter requires official regularization; GT is position-only |
| M2DGR | 21 | USABLE_WITH_ADAPTER | OPEN_CONTROL | MAJOR_ADAPTER | 36 synchronized ground-robot sequences with scenario-specific GT | 1.22 TB and unstable host; per-point timing needs inspection |
| TIERS Enhanced | 21 | USABLE_WITH_ADAPTER | SENSOR_GENERALIZATION | MAJOR_ADAPTER | Corridor/open-road pairing and five heterogeneous LiDARs | Indoor reference is partly SLAM-assisted ICP; frame/extrinsic direction needs inspection |
| SubT-MRS | 20 | LIMITED_USE | PRIMARY_DEGENERATE | MAJOR_ADAPTER | Best tunnel, underground, long-corridor and obscurant relevance | No explicit dataset license found; sensor schema varies by sequence |
| Hilti 2021 | 20 | USABLE_WITH_ADAPTER | SECONDARY_DEGENERATE | MAJOR_ADAPTER | Calibrated construction/basement data; sync within 1 ms | Most GT is sparse 3DoF control, not continuous trajectory truth |
| HeLiPR | 20 | USABLE_WITH_ADAPTER | SENSOR_GENERALIZATION | MAJOR_ADAPTER | Four heterogeneous LiDARs and per-LiDAR 6DoF reference | Main data are asynchronous sensor-specific files; large conversion effort |
| Newer College Original | 19 | USABLE_WITH_ADAPTER | OPEN_CONTROL | MAJOR_ADAPTER | Strong normal open-space control with full trajectory GT | Original sensor streams are software synchronized; processed point fields need inspection |
| MulRan | 18 | USABLE_WITH_ADAPTER | OPEN_CONTROL | MAJOR_ADAPTER | Long-term normal urban routes, official IMU/GPS release and 6DoF baseline | Raw scans lack documented per-point timing; small sample has no IMU/GPS |

The score is the requested sum of twelve 0/1/2 audit items. It does not override license, timing, extrinsic, ground-truth, or sequence-independence constraints.

## Counts and coverage

- Candidate datasets: 10.
- Official-source verified: 10.
- Deep audited: 10.
- Feasibility: 1 `VERIFIED_USABLE`, 8 `USABLE_WITH_ADAPTER`, 1 `LIMITED_USE`, 0 `REJECTED`.
- FAST-LIO2: 0 `DIRECT`, 2 `MINOR_ADAPTER`, 8 `MAJOR_ADAPTER`.
- Explicitly licensed sources: 9. SubT-MRS remains the only license hold.
- Tunnel/underground sources: SubT-MRS and Hilti basement sequences.
- Strong open-control sources: Newer College Original/Extension, NTU VIRAL, M2DGR, MulRan, HeLiPR, TIERS Road3, and MUN-FRL structured DJI flights.
- UAV candidates: MUN-FRL and NTU VIRAL are the primary choices; SubT-MRS has aerial subsets but is not selected as the first UAV adapter target.

## Human decision

The selected role chain is:

1. Primary difficult source: SubT-MRS, conditional on explicit license clarification and a small schema probe.
2. Secondary construction source: Hilti 2021, with sparse-GT metrics kept separate from full-trajectory metrics.
3. Open control: Newer College Multi-Camera Extension, backed by Newer College Original and M2DGR/MulRan road sequences.
4. UAV generalization: MUN-FRL first, NTU VIRAL second.

No Reserved Test sequence is locked in Day 6. The sequence inventory is a proposal only.
