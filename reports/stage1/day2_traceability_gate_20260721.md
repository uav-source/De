# Stage 1 Day 2 Traceability Gate — 2026-07-21

```text
PATENT_DOC_AVAILABLE: true
PATENT_DOC_SHA256: e69b8d2651b4693883dbeecdfe082da6d3cb7b03974d59651af0bb60260a13fc
PATENT_FORMULA_COUNT: 133
CORE_FORMULA_COUNT: 17

FORMULA_EXACT_MATCH_COUNT: 9
FORMULA_EQUIVALENT_COUNT: 1
FORMULA_PARTIAL_COUNT: 6
FORMULA_NOT_IMPLEMENTED_COUNT: 1
FORMULA_CONTRADICTED_COUNT: 0
FORMULA_UNCLEAR_COUNT: 0

CLAIM_CORE_FEATURE_COUNT: 8
CLAIM_FULLY_SUPPORTED_COUNT: 6
CLAIM_PARTIALLY_SUPPORTED_COUNT: 2
CLAIM_UNSUPPORTED_COUNT: 0

OVERCLAIM_COUNT: 4
P0_ISSUE_COUNT: 1
P1_ISSUE_COUNT: 10
P2_ISSUE_COUNT: 3

ORIGINAL_BUNDLE_PERSISTED: true
SUPPLEMENTAL_BUNDLE_CREATED: false
BUNDLE_VERIFY_PASS: true

SCIENTIFIC_CODE_MODIFIED: false
HISTORICAL_ARTIFACTS_MODIFIED: false
FORMAL_EXPERIMENTS_RERUN: false
GIT_PUSH_PERFORMED: false

FULL_PYTEST_COMMAND: python3 -m pytest -q
FULL_PYTEST_PASS: false
FULL_PYTEST_PASSED_COUNT: 184
FULL_PYTEST_FAILED_COUNT: 1
FULL_PYTEST_SKIPPED_COUNT: 0
FULL_PYTEST_EXIT_CODE: 1
FULL_PYTEST_FIRST_ROOT_CAUSE: Day 1 commit tracks two .log files forbidden by tests/test_no_generated_files_tracked.py

DAY2_GATE: TRACEABILITY_FAIL
```

## Baseline verification

- Repository: `/home/lj/Degen-LIO`
- Branch: `feature/weak-update-stage2c`
- Day 1 audit HEAD at Day 2 start: `281c9f31709e8ad8f1aeacbb14ec553fc74d4407`
- Scientific baseline: `ae90aaad51e72aa53ee0344047f9475fb51650a9`
- Archive tag: `archive/stage2c-projected-gain-no-go`
- Tag target: `ae90aaad51e72aa53ee0344047f9475fb51650a9`
- Day 2 initial worktree: clean
- Required Day 1 audit files: present

## Patent source

- External path: `/home/lj/文档/WPS Cloud Files/797344510/0-专利/一种隧道退化环境下激光惯性里程计退化检测与弱方向识别方法_专利技术交底书.docx`
- The DOCX remained outside the repository and was not modified.
- Title: 一种隧道退化环境下激光惯性里程计退化检测与弱方向识别方法——专利技术交底书
- Structure: 359 body paragraphs, 44 headings (H1=5, H2=18, H3=3, H4=18), 4 tables, 4 image placements, 133 native OMML formulas.
- Formula parsing: all 133 objects are `FORMULA_PARSE_PARTIAL`; raw OMML XML and full patent text were not copied into the repository. The 17 core mathematical relations were manually traceable from the OMML structure and adjacent disclosure.
- Host clock observed during the task: 2026-07-15; filenames and task identifier follow the specified execution date 2026-07-21. This provenance discrepancy is disclosed rather than hidden.

## Permanent bundle archive

- Source: `/tmp/degen_lio_stage1_day1/Degen-LIO-stage1-baseline-20260720.bundle`
- Permanent copy: `/home/lj/Degen-LIO-backups/stage1/Degen-LIO-stage1-baseline-20260720.bundle`
- Size: 7,014,441 bytes
- SHA-256: `5386e1a425aa72caf4b3e452fbce334fbedd8b42d542d79fec20fe77013d30f2`
- Expected hash matched: true
- `git bundle verify`: pass; complete history
- Supplemental bundle: not needed

## Gate rationale

The gate is `TRACEABILITY_FAIL`, not an incomplete or warning-only result,
because F13 is a core formula mismatch: the patent normalizes the first
eigengap with `max(lambda1, epsilon_k)`, while frozen code uses
`max(lambda_max, 1e-12)`. The difference affects near-zero spectra. The brief
classifies a patent/core-code formula mismatch as P0, and P0 prevents PASS.

The patent is otherwise unusually careful about the scientific boundary: it
explicitly excludes significant drift reduction, future-risk prediction, and
completed FAST-LIO2/real-IMU/complete-system integration. Those exclusions are
consistent with the Stage 1C, Stage 2B, and Stage 2C negative artifacts and
must remain.

## Issue summary

### P0 — 1

1. F13 eigengap denominator differs from frozen code. Correct the patent text/notation before filing; do not back-edit scientific code to manufacture agreement.

### P1 — 10

1. Real current-prior acquisition/dewarping/association lacks formal evidence.
2. Perturbation and translation coordinate conventions need explicit disclosure.
3. Detector variance whitening, optional Huber weighting, and updater H must be separated.
4. `epsilon_a` parameterization is not aligned/disclosed.
5. Point-count duplication/scaling invariance lacks a direct test.
6. Descending eigenpair binding and primary eigengap rejection lack direct regressions.
7. Temporal direction continuity is not implemented/tested.
8. Quality flags, fallback/hysteresis, and per-frame runtime outputs are absent.
9. Broad platform/framework, independent deployment, and online-suitability statements exceed current real-system evidence.
10. Full pytest fails only `test_no_generated_data_results_or_cache_is_tracked`: Day 1 commit `281c9f3` tracks `reports/stage1/pytest_full_20260720.log` and `reports/stage1/pytest_full_initial_20260720.log`. The failure was preserved rather than changing the test or deleting prior evidence outside Day 2's allowed file list.

### P2 — 3

1. AIS raw/normalized field naming is inconsistent between patent and code.
2. S106 numbering is duplicated/combined inconsistently.
3. Legacy six-dimensional and primary translation metric names coexist and should be disambiguated in patent-facing material.

## Overclaim result

Four positive statements require narrowing: broad platform/scenario use,
frame-by-frame online suitability, framework-independent embedding, and
independent no-GT real deployment. Three additional high-risk phrases occur
only inside explicit exclusion paragraphs (drift reduction, future-risk
prediction, completed integration); they are not counted as active overclaims,
but would become P0 if reintroduced as benefits.

## Safety result

- Scientific code modified: no
- Configuration modified: no
- Existing tests or thresholds modified: no
- Historical artifacts modified: no
- README modified: no
- Formal Stage 1C/2A/2B/2C experiments rerun: no
- Patent DOCX modified or copied into repository: no
- Git push performed: no

## Full pytest

- Command: `python3 -m pytest -q`
- Result: **184 passed, 1 failed, 0 skipped, 1 warning** in 17.55 s; exit code 1
- Failure: `tests/test_no_generated_files_tracked.py::test_no_generated_data_results_or_cache_is_tracked`
- Root cause: the Day 1 audit commit tracks two `.log` report files; the repository contract forbids any tracked `.log`.
- Scientific tests were not weakened, deleted, or edited. The prior Day 1 evidence files were not removed during this Day 2-only report task.
