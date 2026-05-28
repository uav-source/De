# Day 25 Diagnostic Benchmark Paper Outline Report

## Direct Answers

- Day 25 是否完成 diagnostic benchmark paper outline？Yes. It creates title candidates, contribution mapping, section outline, figure/table plan, experiment storyline, claim boundary, reproducibility plan, reviewer response plan, and Day 26 route recommendations.
- 推荐论文标题/定位是什么？Recommended title: "A Diagnostic Benchmark for LiDAR-Inertial Degeneracy in Synthetic Tunnel-Like Scenes". Positioning: benchmark and failure-analysis package.
- 当前论文的核心贡献应该怎么写？Use contribution IDs with scoped wording: `C01, C02, C03, C04, C05, C06`.
- 哪些 claim 可以写？Allowed or scoped claim IDs: `CB05, CB06, CB07`.
- 哪些 claim 绝对不能写？Forbidden claim IDs: `CB01, CB02, CB03, CB04, CB08`.
- 论文图表主线是什么？Start from benchmark geometry and weak-direction diagnostics, then bias audit, unbiased probe, strict metric validity stress tests, gate decision, claim boundary, and reproducibility commands.
- 最大审稿风险是什么？Synthetic-only scope, toy_lio not being real LIO, no estimator method, failed metric validity, and overclaiming risk.
- Day 26 应该做什么？Selected Day 26 options: paper skeleton drafting: draft paper skeleton with section stubs and claim-boundary notes; figure/table generation plan: turn Day25 figure/table plan into reproducible plotting/table scripts or placeholders; README/release cleanup: write release scope, commands, exclusions, and forbidden claims.
- 是否允许进入 weak-subspace update？No.

## Section Outline

Planned sections: Introduction, Related Work, Problem Formulation and Diagnostic Objective, Synthetic Degeneracy Benchmark, Whitened Information and Weak-Direction Diagnostics, Bias Audit and Unbiased Toy Probe, Metric Validity Stress Tests, Go/No-Go Gate and Claim Boundary, Discussion and Limitations, Reproducibility Package, Conclusion.

## Contribution Map

| contribution_id | contribution_text | claim_status |
|---|---|---|
| C01 | synthetic degeneracy benchmark | allowed |
| C02 | weak-direction / whitened information diagnostic protocol | allowed |
| C03 | legacy bias audit and unbiased toy_lio protocol | allowed |
| C04 | strict metric validity negative evidence | allowed |
| C05 | claim-boundary and gate-review framework | allowed |
| C06 | reproducibility package | conditional |
| C07 | validated estimator update | forbidden |

## Figure / Table Plan

| item_id | item_type | paper_section | priority |
|---|---|---|---|
| F01 | figure | Synthetic Degeneracy Benchmark | high |
| F02 | figure | Whitened Information | high |
| F03 | figure | Bias Audit | high |
| T01 | table | Bias Audit | medium |
| T02 | table | Metric Validity Stress Tests | high |
| T03 | table | Metric Validity Stress Tests | high |
| T04 | table | Metric Validity Stress Tests | high |
| T05 | table | Metric Validity Stress Tests | medium |
| T06 | table | Go/No-Go Gate | high |
| T07 | table | Go/No-Go Gate | high |
| T08 | table | Reproducibility Package | high |

## Reviewer Response Snapshot

| risk_id | reviewer_attack | short_response |
|---|---|---|
| RR01 | synthetic-only | We scope the paper as a synthetic diagnostic benchmark, not real-world validation. |
| RR02 | toy_lio not real LIO | toy_lio is presented as a synthetic probe and bias-audit instrument only. |
| RR03 | no estimator method | The gate review explicitly blocks method update and preserves evidence integrity. |
| RR04 | ODI failed validity | We report the failed controlled validity screen as a central negative result. |
| RR05 | joint risk failed gate | All joint-risk candidates are retained as exploratory_not_validated, including no-ODI comparisons. |

## Conclusion

Day 25 converts the diagnostic benchmark evidence into a paper outline and figure-table plan.
The paper should be positioned as a diagnostic benchmark / failure-analysis contribution, not a validated Degen-LIO estimator method.
Weak-subspace update remains unauthorized.
Day 26 should proceed with paper skeleton drafting, figure/table planning, and README/release cleanup.
