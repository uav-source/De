# Day 27 README / Release Cleanup Report

## Direct Answers

- README 是否已经更新为 diagnostic benchmark / failure-analysis 定位？Yes.
- README 是否仍存在 forbidden claims？No.
- release archive 需要排除哪些路径？.git, .pytest_cache, __pycache__.
- 是否已经生成安全 release plan？Yes. `day27_safe_archive_plan.csv` records non-destructive archive options.
- 图表生成哪些 ready，哪些 pending？Ready for conversion: `F02, T01, T02, T03, T04, T05, T06, T07, T08`. Pending: `F01, F03`.
- 是否允许进入 weak-subspace update？No.
- Day 28 应该做什么？Selected options: figure/table generation scripts: implement safe conversion scripts for source_available tables and explicit pending placeholders for figures; paper section drafting: expand paper skeleton sections using claim boundary language.

## Conclusion

Day 27 updates README scope and creates a release hygiene audit for the diagnostic benchmark route.
The repository remains a diagnostic benchmark / failure-analysis package, not a validated Degen-LIO estimator method.
Weak-subspace update remains unauthorized.
Day 28 should proceed with figure/table generation scripts or paper section drafting, not method implementation.
