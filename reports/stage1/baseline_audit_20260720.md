# Stage 1 Day 1 Baseline Audit

任务指定执行日期：2026-07-20

主机实际采集时间：2026-07-15T11:01:24+08:00

最终结论：`BASELINE_FREEZE_PASS_WITH_WARNINGS`

## 1. 仓库状态

- `REPOSITORY_VERIFIED=true`
- Repository root: `/home/lj/Degen-LIO`
- Original/current branch: `feature/weak-update-stage2c`
- Baseline HEAD: `ae90aaad51e72aa53ee0344047f9475fb51650a9`
- Initial worktree clean: `true`
- Initial tracked modified/staged/untracked counts: `0/0/0`
- Worktree at report generation: intentionally dirty with only untracked Day 1 audit outputs
- Remote: none configured (`git remote -v` returned no entries)
- Initial archive tags: `archive/stage1c-confirmatory-no-go`, `archive/detector-stage2a-pass`, `archive/weak-update-stage2b-no-go`
- Required directories present: `src/`, `tests/`, `configs/`, `scripts/`, `artifacts/`, `docs/`
- Verified commits: `d812c39`, `921ea5a`, `e6b0eb4`, `ae90aaa` all exist

Latest 15 commits at audit start:

```text
ae90aaa Record compact Stage 2C audit results
e6b0eb4 feat: freeze projected-gain selective update stage2c
921ea5a Archive Stage 2B column-scaling NO-GO evidence
c5fe3c5 Record compact Stage 2B no-go audit
01cc1ec Freeze Stage 2B update lock
52b6435 Add paired Stage 2B development and locking
9eb76a3 Add deterministic axial correspondence stress
85bacc3 Add covariance-aware MAP update strategies
1c02303 Fix verified pytest subprocess isolation
d812c39 Record Stage 2A confirmation and environment audit
db1fbc7 Freeze Stage 2A detector lock and development audit
974176d Record cleanup audit
a590624 Add locked detector-only Stage 2A validation
6e1e1fe Add nested additive geometry observations
6562189 Fix primary direction and empty subspace semantics
```

## 2. 环境

| Field | Value |
| --- | --- |
| OS | Linux 5.15.0-139-generic x86_64, Ubuntu 20.04-era glibc 2.29 |
| Python | `/usr/bin/python3`, 3.8.10 |
| Python 3.11 | unavailable; required fallback was used |
| NumPy | 1.24.4 |
| SciPy | 1.10.1 |
| pytest | 8.3.5 |

完整环境记录：`reports/stage1/environment_provenance.json`。

## 3. 测试

| Run | Command | Passed | Failed | Skipped | Exit | Log |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Existing baseline, before new audit tests | `python3 -m pytest -q` | 176 | 0 | 0 | 0 | `reports/stage1/pytest_full_initial_20260720.log` |
| Final full suite | `python3 -m pytest -q` | 185 | 0 | 0 | 0 | `reports/stage1/pytest_full_20260720.log` |

Final run also reported one existing `DeprecationWarning` from
`tests/test_huber_normal_equation.py`. Machine-readable provenance is at
`reports/stage1/pytest_provenance.json`; exit code is also preserved at
`reports/stage1/pytest_exit_code.txt`.

## 4. 科学状态

The final status vocabulary below is restricted to `CONFIRMED`, `REJECTED`,
`NOT_IMPLEMENTED`, and `UNCLEAR`. Code availability, Development, reserved
Test, final Gate, and README claims were evaluated separately.

| Item | Code implementation | Development result | Test result | Final Gate | README claim | Audited status | Primary evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Stage 1C risk prediction | Historical evaluation implementation retained | Development evidence retained | `PREDICTION_FAIL` | `RISK_WARNING_AUTHORIZED=false` | Reliable drift prediction and online warning not confirmed | `REJECTED` | `artifacts/history/stage1c_confirmatory_no_go/test/stage1c_gate_report.md`; `artifacts/history/stage1c_confirmatory_no_go/test/test_manifest.json` |
| Stage 2A detector | Detector and weak-direction implementation present | Development lock/evidence present | Detector and direction gates pass | `DETECTOR_PASS`; weak update authorized, risk warning fixed false | Detector and weak direction confirmed | `CONFIRMED` | `artifacts/current/detector_stage2a/detector_stage2a_gate_report.md`; `artifacts/current/detector_stage2a/test_manifest.json` |
| Stage 2B column scaling | Historical implementation/evidence frozen; no active Stage 2B evaluator module in current tree | A locked alpha was evaluated | Both contaminated-severe performance gates fail | `SELECTIVE_UPDATE_PASS=false` | Column-scaled update is a NO-GO | `REJECTED` | `artifacts/history/stage2b_column_scaling_no_go/weak_update_stage2b_gate_report.md`; `artifacts/history/stage2b_column_scaling_no_go/test_manifest.json` |
| Stage 2C projected gain | `src/eval/weak_update_stage2c.py` present | `DEVELOPMENT_PASS`, alpha 0.9 selected | Both coherent-stress performance gates fail | `PROJECTED_GAIN_UPDATE_PASS=false` | Mathematically correct but reserved Test gate failed | `REJECTED` | `artifacts/current/weak_update_stage2c/weak_update_stage2c_gate_report.md`; `artifacts/current/weak_update_stage2c/test_manifest.json` |
| FAST-LIO2 integration | Absent | Not run | Not run | `FAST_LIO2_INTEGRATION_AUTHORIZED=false` | Not implemented | `NOT_IMPLEMENTED` | `README.md`; `docs/weak_update_stage2c.md`; Stage 2C gate report |
| Real IMU propagation | Only a deterministic 6DoF motion surrogate exists; it explicitly is not a full IMU model | Not run | Not run | No authorization | Not implemented | `NOT_IMPLEMENTED` | `README.md`; `src/minibench/motion_simulator.py`; `configs/toy_lio/motion_surrogate_stage2c.yaml` |
| Real data association | Synthetic observation generation exists; real association does not | Not run | Not run | No authorization | Not implemented | `NOT_IMPLEMENTED` | `README.md`; `docs/weak_update_stage2c.md`; `src/minibench/observation_simulator.py` |
| Complete Degen-LIO | Prototype components only | Not run | Not run | No complete-system gate | Not implemented | `NOT_IMPLEMENTED` | `README.md`; `docs/problem_statement.md` |

This audit did not alter ODI, the translation Schur information matrix, weak
direction semantics, or either weak-update algorithm. It did not rerun any
formal Stage 1C/2A/2B/2C experiment.

## 5. Artifact 状态

All requested paths existed. Every manifest was generated twice; the two sets
of JSON/text output hashes were identical. No read errors occurred.

| Group | Exists | Files | Bytes | Manifest | Manifest SHA-256 |
| --- | --- | ---: | ---: | --- | --- |
| Source/config/tests | yes | 162 | 564,763 | `reports/stage1/source_manifest.json` | `7a23fdfba5a68659c6721699f23e94a31b8abe3875d2edbb20b065e92b6fd14d` |
| Stage 2A | yes | 16 | 33,970 | `reports/stage1/stage2a_manifest.json` | `6bf3759a7d8c7a5630df9cb50c559dc4748271491e7ec8c4d248b978d8f9a80b` |
| Stage 1C | yes | 24 | 1,269,181 | `reports/stage1/stage1c_manifest.json` | `70d334915c3cde1a6baca4f3631445915786ee7f39e2c02bf288e3fd776d987e` |
| Stage 2B | yes | 11 | 35,789 | `reports/stage1/stage2b_manifest.json` | `846be5c2fbc36ab8bfc196e8eb5b69ebad6240f28fbd9ecd9dc06c48272e2bd5` |
| Stage 2C | yes | 17 | 124,342 | `reports/stage1/stage2c_manifest.json` | `74645e1f7df20ea67cc6d9486af611103caed003c23e2cfb0933baccd545c574` |

## 6. Git 归档

- Tag: `archive/stage2c-projected-gain-no-go`
- Annotated tag object: `e4186654c31a5851beae7d4169378e1683c77edb`
- Peeled target: `ae90aaad51e72aa53ee0344047f9475fb51650a9`
- Conflict: `false`
- Bundle: `/tmp/degen_lio_stage1_day1/Degen-LIO-stage1-baseline-20260720.bundle`
- Bundle size: 7,014,441 bytes
- Bundle SHA-256: `5386e1a425aa72caf4b3e452fbce334fbedd8b42d542d79fec20fe77013d30f2`
- Bundle verification: success; `git bundle verify` reported a complete history
- Push performed: `false`

The bundle is outside the repository and contains committed refs only; the
uncommitted Day 1 report files are not part of it.

## 7. 异常

### P0 — 影响科学证据或无法冻结

None. Required artifacts are present/readable, tests pass, stable manifests
were reproduced, the tag target is correct, and the bundle verifies.

### P1 — 需要在专利提交前修正

1. The task labels the execution date as 2026-07-20, while the host clock at
   collection time was 2026-07-15. Both values are preserved; filenames follow
   the task-specified date.
2. Python 3.11 was unavailable. Testing used the allowed fallback
   `/usr/bin/python3` 3.8.10. This matches the interpreter recorded in prior
   Stage 2A/2B/2C manifests, but not the README's preferred supported version.

### P2 — 一般工程改进

1. The full suite emits one existing deprecation warning for
   `build_normal_equation`.
2. No Git remote is configured, so the tag and bundle are local-only. No push
   was attempted, as required.

## 8. 最终结论

`BASELINE_FREEZE_PASS_WITH_WARNINGS`

The scientific baseline is auditable and locally frozen. The warning status
is caused by the disclosed task-date/host-date mismatch and Python fallback,
not by hidden scientific failures. Stage 1C, Stage 2B, and Stage 2C remain
NO-GO/REJECTED exactly as their frozen evidence records state; Stage 2A alone
is confirmed.
