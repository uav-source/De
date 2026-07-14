# Frozen Stage 1c Confirmatory NO-GO

This directory is the compact, checksummed audit record retained before the
Detector Consolidation Stage 2A cleanup.

- Original branch: `feature/metric-redesign-stage1c`
- Original result commit: `c1b288b16bf3057bfdb35bbf80ed2a584aeff8df`
- Analysis-lock commit: `134fb68bd69bcdfcbc2579648490309671c289f9`
- Historical tag: `archive/stage1c-confirmatory-no-go`
- Stage 1c gates: `ENGINEERING_PASS`, `MECHANISM_FAIL`, `DETECTOR_FAIL`, `PREDICTION_FAIL`
- Frozen authorizations: `WEAK_UPDATE_AUTHORIZED=false`, `RISK_WARNING_AUTHORIZED=false`
- Current decision: preserve detector and weak-direction work; pause the drift-risk-prediction route.

## Original paths

The `development/` files came from
`results/metric_redesign_stage1c/development/stage1c_dev_v1/`; manifest and
report files retain their original subdirectory meaning. The `test/` files came
from `results/metric_redesign_stage1c/test/stage1c_test_v1/`. The two provenance
records came from `results/metric_redesign_stage1c/test_provenance_run1.json`
and `test_provenance_run2.json`. The pytest diagnosis came from
`reports/stage1c_pytest_diagnosis.md`.

The retained files are the immutable lock, manifests, reports, detector and
historical prediction summaries, level summaries, sensor-run summaries,
process-noise audits, threshold calibration, and verified pytest provenance.
They are historical evidence only; Stage 2A does not reopen risk prediction.

## Reproduction and recovery

Large raw observations, trajectories, process trials, and other generated
files are deliberately omitted. They can be regenerated from the historical
tag using the recorded configurations and seeds:

```bash
git show archive/stage1c-confirmatory-no-go:<path>
```

The local full-history bundle created before cleanup is:

```text
/tmp/Degen-LIO-stage1c-before-cleanup.bundle
```

Restore it into a separate checkout with:

```bash
git clone /tmp/Degen-LIO-stage1c-before-cleanup.bundle Degen-LIO-stage1c-restored
```

Verify the compact evidence from this directory with:

```bash
sha256sum -c SHA256SUMS
```
