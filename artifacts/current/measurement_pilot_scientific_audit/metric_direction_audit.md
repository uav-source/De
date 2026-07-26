# Metric Direction Audit

The frozen positive class is `structural_degeneracy_candidate=1`; `geometry_rich_control=0`.
Score polarity was read from formula/production contracts before inspecting
label performance.  ODI is already a risk score: larger means more spectral
concentration and lower effective rank.

- `ODI_trans`: risk_score = raw_score (more concentrated, lower-effective-rank spectrum).
- `AIS_trans`: risk_score = -raw_score (greater absolute translation information).
- `lambda_min_trans`: risk_score = -raw_score (stronger weakest translation direction).
- `condition_number_trans`: risk_score = raw_score (more ill-conditioned/anisotropic spectrum).
- `lambda_min_over_lambda_max`: risk_score = -raw_score (more balanced minimum-to-maximum information).
- `spectral_entropy_trans`: risk_score = -raw_score (higher effective spectral dimension).
- `effective_rank_trans`: risk_score = -raw_score (higher effective spectral dimension).
- `primary_eigengap`: N/A for degeneration label; -raw is only a direction-unreliability diagnostic (more identifiable minimum-eigenvalue direction (scale dependent)).
- `primary_eigengap_ratio`: N/A for degeneration label; -raw is only a direction-unreliability diagnostic (more identifiable/stable minimum-eigenvalue direction).

ODI raw/semantic/reversed-diagnostic AUROC is
0.001966771906 / 0.001966771906 /
0.998033228094.  The near-one reversed
diagnostic is not a formal result and was never substituted for the semantic
score.  It shows that the frozen labels run opposite to the predeclared risk
semantics.  The original pilot also mislabeled eigengap ratio as
"higher is more degenerate"; high eigengap instead means a more identifiable
weak direction.  The original `abs(Spearman)` effectiveness predicate is also
semantically unsafe, although neither defect changes this pilot's FAIL.
