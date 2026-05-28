# T08

Reproducibility command table. This item supports diagnostic benchmark interpretation only; Diagnostic benchmark evidence only; do not claim full real-render guarantee from smoke path.

Claim boundary: Diagnostic benchmark evidence only; do not claim full real-render guarantee from smoke path.

| repro_step | command | expected_outputs | required_inputs | runtime_expectation | notes |
| --- | --- | --- | --- | --- | --- |
| R00 | python3 scripts/check_env.py | environment manifest/status | repository checkout | seconds | records commit and baseline environment |
| R01 | python3 -m pytest -q | full test suite result | repository checkout | seconds to minutes | must pass before release |
| R02 | bash scripts/reproduce_day14.sh --run | Day14 raw/metrics/tables/figures/manifests | configs and source tree | minutes | uses smoke plot/sensitivity mode for CI stability; real plots can be generated separately |
| R15 | python3 scripts/08_bias_audit.py | Day15 bias audit table/manifest/report | Day14 summaries and reports | seconds | legacy bias audit |
| R16 | python3 scripts/09_run_unbiased_toy_lio.py --config configs/toy_lio/unbiased_day16.yaml | Day16 unbiased summary/manifest/report | Day14 minibench and ODI inputs | seconds | establishes zero applied bias protocol |
| R17 | python3 scripts/10_unbiased_metric_probe.py --config configs/toy_lio/unbiased_day17.yaml | Day17 trial/summary/correlation tables | Day16 protocol and Day14 inputs | minutes | multi-trial exploratory evidence |
| R18 | python3 scripts/11_within_sequence_validation.py --config configs/validation/day18_within_sequence.yaml | Day18 window validation tables | Day17 raw trajectories and ODI inputs | seconds | within-sequence validation |
| R19 | python3 scripts/12_grouped_loso_validation.py --config configs/validation/day19_grouped_loso.yaml | Day19 grouped/LOSO tables | Day18 tables | seconds | generalization stress test |
| R20 | python3 scripts/13_controlled_partial_validity.py --config configs/validation/day20_controlled_partial.yaml | Day20 partial/permutation tables | Day18 and Day19 tables | seconds | controlled incremental validity |
| R21 | python3 scripts/14_joint_risk_features.py --config configs/validation/day21_joint_risk.yaml | Day21 joint-risk tables | Day18 and Day20 tables | seconds | interpretable joint risk screen |
| R22 | python3 scripts/15_day22_gate_review.py --config configs/validation/day22_gate_review.yaml | Day22 gate tables/manifest/report | Day15-21 artifacts | seconds | formal go/no-go gate review |
| R23 | python3 scripts/16_day23_route_b_pivot.py --config configs/validation/day23_route_b_pivot.yaml | Day23 Route B tables/manifest/report | Day18-22 artifacts | seconds | analysis/pivot route |
| R24 | python3 scripts/17_day24_diagnostic_consolidation.py --config configs/validation/day24_diagnostic_consolidation.yaml | Day24 consolidation tables/manifest/report | Day14-23 artifacts | seconds | diagnostic benchmark consolidation |
| R25 | python3 scripts/18_day25_paper_outline.py --config configs/validation/day25_paper_outline.yaml | Day25 paper outline tables/manifest/report | Day14-24 artifacts | seconds | paper outline and figure-table plan |
| R26 | release archive cleanup | archive without .git, __pycache__, .pytest_cache | repository tree | seconds | exclude .git, __pycache__, and .pytest_cache from final package |
