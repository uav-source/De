# Day 23 Route B Pivot Report

## Direct Answers

- Day 23 是否执行了 Route B？Yes. It follows Route B after the Day 22 No-Go gate.
- 为什么 Day 22 No-Go 不是项目失败？Because the negative gate preserves scientific validity and converts unsupported method claims into diagnostic benchmark evidence.
- ODI 单指标失败的主要原因是什么？The single-metric evidence remains weak after within-sequence, grouped/LOSO, and controlled partial screens.
- joint risk 失败的主要原因是什么？All fixed joint-risk features remain exploratory; no feature passed strict controlled validity, and no-ODI variants can be competitive.
- 当前还能支撑哪些论文 claim？Unbiased synthetic protocol, diagnostic benchmark construction, weak-direction geometry analysis, and bias audit lessons.
- 当前不能支撑哪些论文 claim？Forbidden claim IDs: `CL03, CL04, CL05, CL06, CL07`.
- 项目下一步应该走 diagnostic benchmark consolidation，还是 metric redesign？Selected Day 24 options: diagnostic benchmark consolidation: consolidate benchmark package, claim boundaries, and negative metric validity evidence; metric redesign prototype review: review temporal/excitation-normalized diagnostic metric candidates without estimator update.
- Day 24 是否允许 weak-subspace update？No.

## Failure Taxonomy

High / critical failures: `F18, F19, F20, F21, F22`.

## Metric Redesign Candidates

| candidate_id | candidate_name | priority | required_next_test |
|---|---|---|---|
| M01 | temporal_ODI_delta | high | windowed permutation and LOSO |
| M02 | ODI_instability_over_window | high | within-sequence controlled screen |
| M03 | excitation_normalized_lambda | high | controlled partial with path/motion controls |
| M04 | information_drop_rate | medium | LOSO across held-out sequences |
| M05 | weak_alignment_instability | medium | NaN-safe window validation |
| M06 | hybrid_failure_detector_no_method_update | high | benchmark task definition |
| M07 | diagnostic_score_not_control_gain | high | diagnostic benchmark acceptance criteria |

## Diagnostic Benchmark Route

| route_item | paper_claim_strength | recommended_priority |
|---|---|---|
| synthetic degeneracy benchmark | moderate | high |
| weak-direction geometry analysis | moderate | high |
| biased vs unbiased toy_lio lesson | strong diagnostic lesson | high |
| metric validity negative result | moderate but honest | high |
| claim boundary table | strong reproducibility appendix | medium |
| reproducible diagnostic package | strong artifact value | high |
| no method update yet | high integrity | high |

## Conclusion

Day 23 follows Route B after the Day 22 No-Go gate.
The project should not implement weak-subspace update yet.
The evidence supports a diagnostic benchmark / metric-redesign route, not a validated Degen-LIO method route.
Day 24 should continue with diagnostic consolidation or metric redesign review.
