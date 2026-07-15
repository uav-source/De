# Patent–Formula–Code–Test Traceability — 2026-07-21

## Audit identity and boundary

- Patent: 一种隧道退化环境下激光惯性里程计退化检测与弱方向识别方法
- External DOCX SHA-256: `e69b8d2651b4693883dbeecdfe082da6d3cb7b03974d59651af0bb60260a13fc`
- Scientific baseline: `ae90aaad51e72aa53ee0344047f9475fb51650a9`
- Day 1 audit commit: `281c9f31709e8ad8f1aeacbb14ec553fc74d4407`
- Current branch during audit: `feature/weak-update-stage2c`
- Scientific code/config/artifacts were read at the frozen baseline and were not modified.
- The DOCX contains 133 native `m:oMath` objects. Flattened text is not a reliable LaTeX conversion, so every inventory row is marked `FORMULA_PARSE_PARTIAL`; the 17 core relations below were audited from their OMML structure, variables, and adjacent disclosure without inventing missing operators.

## Status totals

| Status | Count |
| --- | ---: |
| `EXACT_MATCH` | 9 |
| `EQUIVALENT_IMPLEMENTATION` | 1 |
| `PARTIAL_MATCH` | 6 |
| `NOT_IMPLEMENTED` | 1 |
| `CONTRADICTED_BY_RESULTS` | 0 |
| `UNCLEAR` | 0 |
| Total | 17 |

## Core traceability table

| ID | Patent relation | Frozen implementation | Principal test/evidence | Status | Issue |
| --- | --- | --- | --- | --- | --- |
| F01 | Prior point-to-plane residual | `map_lio.linearize_point_to_plane`, lines 20–43 | `test_point_to_plane_is_relinearized_at_prior_pose`; Stage 2C artifact | `PARTIAL_MATCH` | Stage 2C adds stored base noise; Stage 2A formal detector evidence uses synthetic precomputed Jacobians rather than a real online prior/correspondence path. |
| F02 | Six-DoF Jacobian `[nᵀ(-R[p]×), nᵀ]` | `linearize_point_to_plane`; `compute_point_to_plane_jacobian` | Jacobian translation-block unit test | `EXACT_MATCH` | Patent must state right rotation perturbation and world-additive translation explicitly. |
| F03 | Variance whitening and optional Huber weighting | Detector `compute_H_tilde`; updater `build_robust_linear_system` | Robust direct-normal-equation test | `PARTIAL_MATCH` | Noise whitening is in the detector; Huber weighting is only in the updater. They must not be conflated. |
| F04 | `D=diag(sθI3,spI3)` and Jacobian right multiplication | `compute_H_tilde`, lines 10–37 | Formula-contract and PSD tests | `EXACT_MATCH` | Example values 0.05 rad and 0.5 m are correctly non-universal. |
| F05 | Scale-consistent six-dimensional detector information | `compute_H_tilde`; separate updater normal equation | Whitened-info and robust-system tests | `PARTIAL_MATCH` | Frozen detector H uses inverse variance and D; updater H uses Huber precision without D. |
| F06 | Damped translation Schur information | `compute_translation_schur_info`, lines 85–111 | Direct block formula, PSD, Stage 2A formal evidence | `EXACT_MATCH` | Uses solve, symmetry restoration, PSD rejection, and roundoff-only clipping as disclosed. |
| F07 | Effective sample count | `compute_effective_sample_size`, lines 114–121 | N_eff unit test; Stage 2A observation mechanism | `PARTIAL_MATCH` | Uses inverse variance only, matching the patent only for the implemented `omega=1` detector case. |
| F08 | `H_t=H_t_raw/N_eff` | `normalize_information_matrix`, lines 124–130 | N_eff normalization unit test | `EXACT_MATCH` | Direct duplicate-measurement/point-count scaling invariance test is missing. |
| F09 | Descending eigenvalue order | `eigen_decompose`, lines 40–47 | Weak-direction test and Stage 2A formal direction evidence | `EXACT_MATCH` | No direct regression asserts descending values and correspondingly reordered columns. |
| F10 | Three-dimensional effective rank and ODI | `compute_effective_rank`; `compute_ODI`; `compute_epsilon` | ODI range/extreme-spectrum tests and Stage 2A detector pass | `EQUIVALENT_IMPLEMENTATION` | Code reuses `epsilon_ratio` as both relative factor and absolute floor and adds clipping; patent names a separate `epsilon_a`. |
| F11 | AIS, minimum eigenvalue, safe condition number | `compute_AIS`; `compute_lambda_min`; `safe_condition_number` | Scale-stability tests; formal metric outputs | `EXACT_MATCH` | Eigenvalue-log implementation is equivalent to logdet. |
| F12 | Minimum translation eigenvector as an unoriented weak axis | `estimate_primary_direction`; `_canonical_sign` | Sign-invariance and no-GT tests; Stage 2A direction pass | `EXACT_MATCH` | Runtime direction is world-frame and does not consume GT; GT axis is evaluation-only. |
| F13 | Normalized first eigengap | `estimate_primary_direction`, lines 26–52 | Primary-direction unit test; Stage 2A stability gate | `PARTIAL_MATCH` | **P0:** patent denominator is `max(lambda1, epsilon_k)`; code uses `max(lambda_max, 1e-12)`. |
| F14 | Optional temporal direction continuity | No detector implementation | No test/artifact | `NOT_IMPLEMENTED` | Window/persistence, interruption, first-frame, and temporal rejection semantics are absent. |
| F15 | `actionable = triggered AND stable` | `evaluate_trigger_direction_state`, lines 52–61 | Direct truth-table test; Stage 2A state gates | `EXACT_MATCH` | No extra condition is used in the formal detector. |
| F16 | Open-Control Development 0.95 quantile | `calibrate_odi_trigger_threshold`, lines 29–39 | Direct calibration test and frozen lock | `EXACT_MATCH` | Threshold is dataset/sensor/config-specific, not universal. |
| F17 | Output and non-output boundary | `compute_metrics_for_frame/sequence` | Output/no-GT tests plus Stage 1C/2B/2C negative artifacts | `PARTIAL_MATCH` | Core metrics/states exist; quality flags, hysteresis, explicit invalid-result fallback, and per-frame runtime output do not. |

The complete row-level fields required by the brief, including configuration
keys, test names, artifact paths, evidence level, and recommended action, are
in `reports/stage1/formula_code_traceability_20260721.csv`.

## Required mathematical-property test audit

| Property | Evidence | Result |
| --- | --- | --- |
| Schur symmetry | Implementation symmetrizes; direct block-formula test compares full result | Present |
| Schur PSD | `test_translation_schur_matches_block_formula` asserts nonnegative eigenvalues | Present |
| Point-count scaling invariance | No direct duplicate-measurement or scaled-count test | **Missing — P1** |
| ODI range | `test_condition_number_can_explode_but_ODI_remains_finite` | Present |
| ODI monotonic response | Stage 2A formal geometry/observation detector gates | Present |
| Eigenvalue sorting | Exercised indirectly; no direct descending-order/column-binding assertion | **Direct test missing — P1** |
| Weak-direction alignment | Unit/integration tests and Stage 2A severe alignment gates | Present |
| Eigenvector sign invariance | `test_eigenvector_sign_does_not_change_alignment` | Present |
| Eigengap rejection | Passing case tested; no direct primary-estimator below-threshold rejection test | **Direct rejection test missing — P1** |
| Actionable truth table | `test_trigger_and_direction_stability_are_independent` | Present |
| GT deletion invariance | `test_runtime_detector_outputs_do_not_depend_on_gt_axis_or_pose` | Present |

No tests were added today to conceal these gaps.

## Stage-specific computation location

- Stage 2A detector confirmation uses synthetic per-frame Jacobians generated at the synthetic sensor pose and consumes `J` plus `R_diag`; residual values do not enter detector metrics.
- Stage 2C relinearizes residual and Jacobian at the propagated prior in `map_lio.linearize_point_to_plane`.
- Stage 2C invokes the same variance-only detector first, then constructs a separate Huber-whitened update system. The detector information matrix and update normal equation are not interchangeable.
- The isolated Stage 2C oracle comparator can receive GT directions, but it is explicitly offline diagnostic-only. The formal detector and primary projected-gain method do not receive GT direction; this is not a GT leak into the detector.

## Technical-effect evidence mapping

| Technical effect or statement | Classification | Evidence and boundary |
| --- | --- | --- |
| Identify controlled degradation severity | `SUPPORTED` | Stage 2A `DETECTOR_PASS`; geometry/observation correlations and monotonic gates passed. |
| Identify the primary weak translation direction | `SUPPORTED` | Stage 2A direction/alignment/stability gates passed. |
| Remove rotation coupling through Schur marginalization | `PARTIALLY_SUPPORTED` | Formula, code, and unit properties match; no separate real-data ablation proves an end-system improvement. |
| Significantly reduce axial drift | `CONTRADICTED` | Stage 2B and Stage 2C performance gates failed; must remain excluded. |
| Predict future localization failure/risk | `CONTRADICTED` | Stage 1C prediction gate failed and risk warning is unauthorized. |
| Operate in real time | `NOT_TESTED` | Complexity is small, but no target-platform latency/deadline artifact exists. |
| Compute detector outputs without GT pose/axis | `SUPPORTED` | Direct deletion-invariance test plus Stage 2A engineering evidence. |
| Directly integrate into FAST-LIO2 | `NOT_TESTED` | No FAST-LIO2 integration exists; only an interface possibility is supportable. |
| Use real IMU propagation and real data association | `NOT_TESTED` | Only a motion surrogate and synthetic observations exist. |
| Transfer unchanged to arbitrary sensors/tunnels | `UNSUPPORTED` | Threshold and scale parameters are frozen for controlled synthetic configurations and require recalibration. |

## Issues

### P0 — 1

1. F13 core eigengap formula denominator differs between the patent and frozen code. This must be corrected in the patent/disclosure before filing; frozen scientific code was not changed.

### P1 — 10

1. Formal detector evidence is synthetic; real current-prior acquisition, dewarping, and correspondence are not integrated.
2. The patent does not explicitly state the implemented right-rotation/world-translation perturbation convention.
3. Patent wording can conflate optional Huber detector weighting with the frozen variance-only detector and with the distinct updater normal equation.
4. The patent names an independent `epsilon_a`, while code reuses `epsilon_ratio` as the floor and the embodiment table omits `epsilon_a`.
5. No direct point-count/duplicate-measurement scaling-invariance test exists.
6. Direct regressions for descending eigenpair binding and below-threshold primary eigengap rejection are missing.
7. Optional temporal continuity/persistence is not implemented or tested; `window_size/window_stride` are not detector-stability parameters.
8. Claimed quality flags, invalid-result fallback, hysteresis, and per-frame runtime outputs are absent.
9. Broad platform/framework applicability, independent real deployment, and online suitability lack real-system/latency evidence.
10. The current full pytest has one audit-hygiene failure because Day 1 commit `281c9f3` tracks two `.log` files, violating `test_no_generated_files_tracked`; all other 184 tests pass. Day 2 did not alter that prior evidence or the test threshold.

### P2 — 3

1. Patent `AIS_t` terminology maps to code fields `AIS_trans_raw` and `AIS_trans_normalized`; the exact field should be named consistently.
2. Both 2.2.7 and 2.2.8 carry step label S106 while the figure legend combines normalization and spectrum decomposition; step references should be normalized.
3. Code retains legacy six-dimensional `ODI`/`AIS` beside the primary translation fields; patent-facing material should consistently identify `ODI_trans` and translation metrics.

## Traceability conclusion

The detector, Schur, ODI, weak-axis, state-separation, threshold-calibration,
and no-GT boundaries have substantial traceable support. The audit cannot pass,
because the core eigengap denominator is not identical to the frozen
implementation. Negative Stage 1C/2B/2C results are correctly excluded in the
current disclosure and must remain excluded.
