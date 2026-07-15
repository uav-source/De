# Stage 1 Day 2 Revision 2 Traceability Gate — 2026-07-21

```text
PATENT_REVISION_AVAILABLE: true
PATENT_REVISION_PATH: /home/lj/Degen-LIO-private-IP/patent1/patent1_degen_lio_v1_2_agent_review.docx
PATENT_REVISION_SHA256: 2f63a53c01eb8c86e3c8003d48453698fe78867cb6b4e31b8ddc5ca55828d5f4

SOURCE_OMML_FORMULA_COUNT: 113
OUTPUT_OMML_FORMULA_COUNT: 113

F13_FORMULA_MATCH: true
EPSILON_G_VALUE: 1e-12
EPSILON_K_AND_G_SEPARATED: true

SCHUR_WORDING_FIXED: true
ROBUST_WEIGHT_OPTIONAL: true
TEMPORAL_CONTINUITY_OPTIONAL: true
REALTIME_OVERCLAIM_FIXED: true
FRAMEWORK_OVERCLAIM_FIXED: true
PLACEHOLDER_COUNT: 0
DUPLICATE_STEP_NUMBERING_FIXED: true
FIGURE1_PAGEBREAK_FIXED: true
FIGURE4_OPTIONAL_OUTPUT_CLARIFIED: true

P0_ISSUE_COUNT: 0
P1_ISSUE_COUNT: 5
P2_ISSUE_COUNT: 1

FULL_PYTEST_COMMAND: python3 -m pytest -q
FULL_PYTEST_PASS: true
FULL_PYTEST_PASSED_COUNT: 185
FULL_PYTEST_FAILED_COUNT: 0
FULL_PYTEST_SKIPPED_COUNT: 0
FULL_PYTEST_EXIT_CODE: 0

TRACKED_LOG_FILE_COUNT: 0
SCIENTIFIC_CODE_MODIFIED: false
HISTORICAL_ARTIFACTS_MODIFIED: false
FORMAL_EXPERIMENTS_RERUN: false
GIT_PUSH_PERFORMED: false

DAY2_GATE: TRACEABILITY_PASS_WITH_WARNINGS
```

## Source and output provenance

- Actual source: `/home/lj/文档/WPS Cloud Files/.797344510/cachedata/72D3CC71690F4C458961BD03DB60CF46/一种隧道退化环境下激光惯性里程计退化检测与弱方向识别方法_专利技术交底书_V1.1_公式一致性修订.docx`
- Source SHA-256: `62dcd24baf3c75e74562524633883a01045cc3b9f7dee06ed103afb5d6767777`
- Source observed modified time: `2026-07-15T12:25:57+08:00`
- Read-only baseline: `/home/lj/Degen-LIO-private-IP/patent1/patent1_degen_lio_v1_1_source.docx`
- Rollback copy: `/home/lj/Degen-LIO-private-IP/patent1/patent1_degen_lio_v1_1_source_rollback.docx`
- Canonical V1.2 output: `/home/lj/Degen-LIO-private-IP/patent1/patent1_degen_lio_v1_2_agent_review.docx`
- Required-name copy: `/home/lj/Degen-LIO-private-IP/patent1/一种隧道退化环境下激光惯性里程计退化检测与弱方向识别方法_专利技术交底书_V1.2_代理人送审版.docx`
- Both output paths are byte-identical and have SHA-256 `2f63a53c01eb8c86e3c8003d48453698fe78867cb6b4e31b8ddc5ca55828d5f4`.
- The DOCX, inspection PDF/PNGs, and private revision reports remain outside the Git repository.

The exact `*专利技术交底书(4).docx` filename was absent. The exact-search result
contained one V1.1 formula-revision candidate, and its synced no-version-name
copy was byte-identical. Older files had different hashes and lacked the
revised F13/`epsilon_g` markers, so the input revision was unique by content.

## Formula and code traceability

The source and output each contain 113 Word-native `m:oMath` formula objects.
Canonical XML hashes for the complete formula sequence are identical. No
formula was converted to an image or plain text.

The output F13 remains a native fraction:

```text
numerator:   lambda_2,k - lambda_3,k
denominator: max(lambda_1,k, epsilon_g)
epsilon_g:   1e-12
```

Frozen code evaluates
`(lambda_next - lambda_min) / max(lambda_max, 1e-12)`, with
`lambda_1=lambda_max`, `lambda_2=lambda_next`, and
`lambda_3=lambda_min`. The formula is an exact match. The patent separately
defines `epsilon_k` for ODI/AIS/condition-number spectrum regularization and
`epsilon_g` only for the eigengap denominator floor.

## Cleanup result

- Schur wording now says that rotation is marginalized and cross-information is accounted for; it does not claim complete coupling removal.
- Residual-variance noise whitening remains in the core chain; Huber or another nonnegative robust weight is optional.
- Alternative residuals are optional embodiments and are not presented as fully validated or necessary independent-claim limitations.
- Temporal continuity, hysteresis, fallback semantics, and quality flags are optional engineering enhancements.
- Real-time operation is conditioned on residual count, processor, estimator, and processing rate measurements.
- Filter/optimizer/scan-matching integration is interface-based and requires target-specific adaptation.
- Output-field mappings identify `ODI_trans`, normalized/raw AIS and minimum-eigenvalue fields, `condition_number_trans`, primary direction/eigengap, and the three separated state fields.
- S106A/S106B through S109A/S109B are synchronized in headings, the execution flow, Figure 1, and the figure-marker paragraph. No bare duplicate S106-S109 marker remains.
- Specified template placeholder count is zero; applicant/inventor/contact fields remain unfilled.
- Figure 1 begins on a new page and its complete marker paragraph is kept together.
- Figure 4's unchanged raster is directly followed by a caption stating that its quality flag is optional.

## Visual verification

The final DOCX was rendered locally to an inspection PDF. It is A4 and has 20
continuously numbered pages. The cover, formula-heavy pages, Schur, ODI/AIS,
F13/eigengap, tables, figure-description page, Figures 1-4, and last page were
checked individually; a full-page contact sheet was also reviewed.

```text
RENDERED_PAGE_COUNT: 20
FORMULA_TRUNCATION_FOUND: false
TABLE_OVERFLOW_FOUND: false
IMAGE_BLUR_OR_CLIPPING_FOUND: false
ORPHAN_HEADING_OR_FIGURE_FOUND: false
BLANK_PAGE_COUNT: 0
VISUAL_CHECK_RESULT: PASS
```

Detailed private reports:

- `/home/lj/Degen-LIO-private-IP/patent1/patent1_v1_2_revision_report.md`
- `/home/lj/Degen-LIO-private-IP/patent1/patent1_v1_2_change_summary.md`

## Remaining P1 warnings — 5

1. Formal detector evidence remains controlled/synthetic; real current-prior acquisition, dewarping, and correspondence integration is not demonstrated.
2. No direct duplicate-measurement or point-count scaling-invariance regression exists.
3. Direct regressions for descending eigenpair binding and below-threshold primary-eigengap rejection remain missing.
4. Optional robust-detector weighting, alternative residuals, temporal continuity, hysteresis, fallback, and quality flags remain unimplemented or not formally validated; V1.2 now labels them optional.
5. Real target-platform framework integration and latency/real-time performance remain unvalidated; V1.2 now limits the claims accordingly.

## Remaining P2 warning — 1

1. Legacy six-dimensional `ODI`/`AIS` fields coexist with the primary translation metrics in frozen code. V1.2 provides explicit translation-field mappings, but future code-facing material must continue to distinguish them.

## Safety and gate conclusion

No `src/`, `configs/`, `artifacts/`, `tests/`, or `README.md` scientific
content changed. No Stage 1C/2A/2B/2C formal experiment was rerun. No `.log`
is tracked and no push was performed. With F13 matched, P0 at zero, the full
suite passing, and no scientific or historical-artifact changes, the final
gate is `TRACEABILITY_PASS_WITH_WARNINGS`.

Host time observed while closing the report was `2026-07-15T13:09:24+08:00`;
the report filename and execution label follow the specified date 2026-07-21.
