# Day 15 Report - Bias Audit

## Decision Context

Day 14 remains **CONDITIONAL GO**. Day 15 does not modify `toy_lio`, does not change ODI/statistics, and does not upgrade the Day 14 conclusion.

## Direct Answers

- Day 7 toy_lio 是否存在 scene-family-dependent axis_bias？Yes. **legacy toy_lio has scene-family-dependent axis_bias**: `{'OC': 0.0, 'CT': 0.016, 'RT': 0.026, 'ST': 0.022}`.
- merged ODI-drift correlation 是否可能被 scene-family confound 放大？Yes. legacy toy_lio injects different axis_bias values by scene family; tunnel scenes also have larger axis error and higher ODI, so merged correlation can be inflated.
- Day 15-30 是否允许继续使用 legacy biased toy_lio 作为主证据？No. Legacy biased toy_lio can only be diagnostic evidence, not Day 15-30 main evidence.
- 哪些旧结果只能作为 diagnostic，不可作为主 claim？Day 7 toy trajectory drift, Day 8 metrics computed from that trajectory, Day 10 merged correlation, and Day 11/14 visual summaries based on the biased toy probe.

## Bias Audit Table

| sequence_id | scene_family | legacy_axis_bias | final_axis_error | ODI_median | axis_drift_rate_median | confound_risk_level |
|---|---:|---:|---:|---:|---:|---|
| OC-L0-S01-M1 | OC | 0 | 1.65278456592e-05 | 0.512430200765 | 1.14963498774e-05 | LOW |
| ST-L3-S01-M1 | ST | 0.022 | 5.22259826916 | 0.728798907088 | 0.0433005779284 | HIGH |
| CT-L2-S01-M2 | CT | 0.016 | 3.47932217494 | 0.728232401037 | 0.0344094216499 | HIGH |
| RT-L4-S01-M1 | RT | 0.026 | 6.7172310564 | 0.728770434587 | 0.0479151494618 | HIGH |

## Interpretation

The legacy process-noise branch uses scene family to choose different axis-bias values. OC has zero legacy axis bias, while tunnel-like sequences have nonzero axis bias. Because the same scene families also differ in ODI and axis drift, merged all-sequence correlation can reflect a scene-label confound.

The Day 15-30 program must therefore replace this with unbiased perturbations before using drift correlations as main evidence. Legacy Day 14 results remain useful for debugging geometry, weak direction extraction, and reproduction discipline, but they are not sufficient for a main metric-validity claim.

## Inputs Checked

- `src/minibench/toy_lio.py`
- `results/day14/tables/day07_toy_lio_summary.csv`
- `results/day14/tables/day08_metric_summary.csv`
- `results/day14/tables/day10_metric_validity.csv`
- `reports/day10_report.md`

## Required Next Step

Day 16 may separate legacy biased and unbiased toy configurations. It must not reuse scene-family axis bias as main evidence.
