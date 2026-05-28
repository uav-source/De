# Table Interpretation Notes

These notes are part of the paper safety layer. They preserve negative evidence and prevent computable statuses from being read as substantive scientific validity.

## T03 - ambiguous validity wording

Ambiguous text: `held_out_validity_status = valid`

Required note: valid means computable, not substantive validity; held-out rows still require effect-size and claim-boundary interpretation

Reason: prevents LOSO computability from being read as scientific success

## T03 - ambiguous validity wording

Ambiguous text: `remains valid`

Required note: valid means computable, not substantive validity; do not present LOSO status as robust generalization

Reason: preserves Day19 negative evidence

## T05 - baseline comparison ambiguity

Ambiguous text: `beats_no_odi_baseline for no-ODI baseline`

Required note: no-ODI baseline cannot beat itself; interpret this field only for with-ODI joint features

Reason: prevents circular baseline interpretation

## T05 - status overread risk

Ambiguous text: `exploratory_not_validated rows`

Required note: exploratory_not_validated means the feature did not pass the strict Day21 gate

Reason: prevents exploratory rows from being cited as validated predictors
