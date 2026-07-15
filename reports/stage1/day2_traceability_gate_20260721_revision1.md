# Stage 1 Day 2 Revision 1 Traceability Gate — 2026-07-21

```text
PATENT_REVISION_AVAILABLE: true
PATENT_REVISION_SHA256: 62dcd24baf3c75e74562524633883a01045cc3b9f7dee06ed103afb5d6767777
F13_FORMULA_MATCH: true
F13_ISSUE_LEVEL: RESOLVED

P0_ISSUE_COUNT: 0
P1_ISSUE_COUNT: 9
P2_ISSUE_COUNT: 3

FULL_PYTEST_COMMAND: python3 -m pytest -q
FULL_PYTEST_PASS: true
FULL_PYTEST_PASSED_COUNT: 185
FULL_PYTEST_FAILED_COUNT: 0
FULL_PYTEST_SKIPPED_COUNT: 0
FULL_PYTEST_EXIT_CODE: 0

LOG_FILES_BACKED_UP: true
LOG_FILES_UNTRACKED: true
TRACKED_LOG_FILE_COUNT: 0

SCIENTIFIC_CODE_MODIFIED: false
HISTORICAL_ARTIFACTS_MODIFIED: false
FORMAL_EXPERIMENTS_RERUN: false
GIT_PUSH_PERFORMED: false

DAY2_GATE: TRACEABILITY_PASS_WITH_WARNINGS
```

## Revision source

- External patent path: `/home/lj/文档/WPS Cloud Files/797344510/0-专利/一种隧道退化环境下激光惯性里程计退化检测与弱方向识别方法_专利技术交底书_V1.1_公式一致性修订.docx`
- SHA-256: `62dcd24baf3c75e74562524633883a01045cc3b9f7dee06ed103afb5d6767777`
- The same SHA was observed for the WPS cache copy.
- The DOCX remained outside the repository and was read only.
- The pre-revision report `reports/stage1/day2_traceability_gate_20260721.md` remains unchanged as failure-state evidence.

## F13 resolution

The V1.1 native Word equation at paragraph P151 is a fraction with:

- numerator: `lambda_2,k - lambda_3,k`;
- denominator: `max(lambda_1,k, epsilon_g)`.

Paragraph P154 and the embodiment parameter table specify
`epsilon_g = 1 x 10^-12`. The table also says that this floor only prevents a
zero eigengap denominator and is separate from the ODI spectral regularizer
`epsilon_k`.

The frozen implementation in `src/degen_detector/weak_direction.py` sorts the
spectrum in ascending order and maps:

- `lambda_1 = lambda_max = ordered[-1]`;
- `lambda_2 = lambda_next = ordered[1]`;
- `lambda_3 = lambda_min = ordered[0]`.

It evaluates
`(lambda_next - lambda_min) / max(lambda_max, 1.0e-12)`. The patent and frozen
implementation therefore agree for both ordinary and near-zero spectra.
`F13_FORMULA_MATCH=true`, and the former P0 is resolved without changing
scientific code.

## Boundary verification

- V1.1 P155-P157 and P325 make temporal continuity an optional engineering enhancement, not part of the frozen core chain.
- V1.1 P211, P218, P231, P344 and the figure descriptions make quality flags and hysteresis optional.
- V1.1 P346-P351 explicitly prevent presenting selective LiDAR-information attenuation, future failure/risk prediction, or completed FAST-LIO2/real-IMU/complete-system integration as proven effects.
- V1.1 P056 says frame-by-frame real-time compliance requires platform-specific measurement; it does not claim that real-time operation has been proved.
- The negative Stage 1C, Stage 2B, and Stage 2C evidence remains unchanged. No formal experiment was rerun.

## P1 warnings — 9

These inherited warnings remain non-blocking and are not deleted by the F13
correction. Where V1.1 improves wording, the residual implementation or
evidence boundary is retained explicitly.

1. Formal detector evidence remains controlled/synthetic; real current-prior acquisition, dewarping, and correspondence are not integrated.
2. V1.1 now states the right-rotation/world-translation convention, but this remains an implementation-specific convention whose target-system adaptation is not validated.
3. V1.1 separates variance whitening from optional robust weighting; the optional robust-detector embodiment remains unfrozen and must not be conflated with the distinct updater normal equation.
4. V1.1 discloses the frozen `epsilon_a=10^-6` parameterization; other epsilon modes or parameterizations remain outside the formal evidence.
5. No direct point-count or duplicate-measurement scaling-invariance regression exists.
6. Direct regressions for descending eigenpair binding and below-threshold primary eigengap rejection are still missing.
7. Optional temporal continuity and persistence are not implemented or tested.
8. Optional quality flags, invalid-result fallback, hysteresis, and per-frame runtime outputs are not frozen detector outputs.
9. Broad platform/framework applicability, independent real deployment, and real-time suitability still lack real-system and latency evidence; V1.1 correctly narrows these statements.

The former tenth P1 issue was the tracked `.log` hygiene failure. It is closed:
both logs are permanently backed up, no `.log` is tracked, and the complete
pytest suite passes.

## P2 warnings — 3

1. V1.1 clarifies normalized/raw AIS names, while historical traceability material and legacy code fields still require care when mapping exact names.
2. V1.1 corrects the duplicate S106 labels to S106A/S106B; the old V1.0 audit remains preserved and therefore retains the historical numbering discrepancy.
3. Legacy six-dimensional `ODI`/`AIS` and primary translation metric names coexist in code; patent-facing interpretation must continue to identify `ODI_trans` and translation metrics explicitly.

## Test and log hygiene

- Revision test summary: `reports/stage1/pytest_revision1_20260721.json`
- Result before final commit: `185 passed, 0 failed, 0 skipped, 1 warning`; exit code 0.
- Permanent log backup directory: `/home/lj/Degen-LIO-backups/stage1/day1-logs/`
- `git ls-files '*.log'`: no output.
- The two working-tree log copies remain ignored by the existing `*.log` rule and are not part of this revision commit.

## Safety conclusion

No scientific source, configuration, test threshold, README, or historical
artifact was changed. No Stage 1C/2A/2B/2C formal experiment was rerun and no
push was performed. With F13 matched, P0 at zero, the full suite passing, and
zero tracked log files, the final gate is
`TRACEABILITY_PASS_WITH_WARNINGS`.
