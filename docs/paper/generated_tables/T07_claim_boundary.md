# T07

Claim boundary table for paper writing. This item supports diagnostic benchmark interpretation only; Diagnostic benchmark evidence only; do not claim forbidden claims as conclusions.

Claim boundary: Diagnostic benchmark evidence only; do not claim forbidden claims as conclusions.

| claim_id | claim_text | status | allowed_wording | forbidden_wording | where_to_use | where_to_avoid | evidence_basis |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CB01 | ODI robustly predicts drift | forbidden | ODI remains exploratory in this benchmark. | Do not use this robust ODI wording. | nowhere | title, abstract, conclusion, contribution list | Day19-21 negative validation screens |
| CB02 | ODI is superior to AIS/lambda_min | forbidden | ODI should be reported beside AIS, lambda_min_clamped, and condition_number. | Do not claim ODI superiority. | comparison limitations | abstract and conclusion | Day10/19/20 baseline competition |
| CB03 | Degen-LIO estimator method is validated | forbidden | The package does not validate a Degen-LIO estimator method. | Do not present an estimator method as validated. | limitations only | title, contribution list, conclusion | Day22 method_update_authorized=false |
| CB04 | weak-subspace update is authorized | forbidden | Weak-subspace update remains unauthorized. | Do not implement or claim update authorization. | gate review only | method section | Day21/22 weak_update_authorized=false |
| CB05 | diagnostic benchmark is reproducible | conditional | The diagnostic benchmark package is reproducible under recorded scripts and manifests. | Do not imply full real-world estimator validation. | artifact and reproducibility sections | method-validation claims | Day13/14/24 manifests and release checklist |
| CB06 | legacy biased toy_lio is diagnostic only | allowed | Legacy biased toy_lio is useful as a bias-audit lesson only. | Do not use legacy biased toy_lio as main metric evidence. | bias audit and limitations | metric validity claims | Day15 bias audit |
| CB07 | negative metric-validity evidence is informative | allowed | Negative metric-validity evidence identifies failure modes and redesign needs. | Do not hide negative screens or rebrand them as validation. | discussion and failure analysis | contribution list as metric success | Day18-24 negative evidence chain |
| CB08 | joint risk features are validated predictors | forbidden | Joint risk features are exploratory diagnostics. | Do not present joint risk as validated. | future work | results conclusion | Day21 all features exploratory_not_validated |
