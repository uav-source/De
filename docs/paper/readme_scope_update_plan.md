# README Scope Update Plan

| readme_section | required_update | reason | allowed_wording | forbidden_wording | blocking |
| --- | --- | --- | --- | --- | --- |
| Project scope | State that this is a diagnostic benchmark / failure-analysis package. | prevents method overclaiming | This repository provides a reproducible diagnostic benchmark for LIO degeneracy analysis. | Do not describe this repository as a validated Degen-LIO estimator method. | true |
| Estimator method boundary | State that Degen-LIO estimator update is not validated or implemented. | matches Day22/24 gates | No estimator update is authorized by the current evidence chain. | Do not claim an estimator method contribution. | true |
| Weak update boundary | State that weak-subspace update remains unauthorized. | prevents premature implementation claims | Weak-subspace update remains gated and unauthorized. | Do not provide instructions as if update logic exists. | true |
| Reproduction commands | List check_env, pytest, reproduce_day14, and Day15-Day26 scripts. | artifact reviewers need exact commands | Run the commands in order to rebuild diagnostics and tables. | Do not imply hidden manual steps. | true |
| Smoke vs real plot distinction | Explain that Day14 reproduction uses smoke plotting/sensitivity for CI stability while real plot scripts remain available. | avoids reproducibility confusion | Smoke mode validates file/manifest structure; real rendering can be run separately. | Do not state smoke figures are full real-rendered figures. | true |
| Forbidden claims | Include a claim-boundary list from Day25/26. | writing guardrail | Use claim-boundary tables before drafting abstracts or conclusions. | Do not include robust ODI drift-prediction wording. | true |
| Release package contents | List configs, scripts, tests, reports, and selected tables/manifests. | clarifies artifact scope | Generated raw data may be rebuilt by scripts unless explicitly packaged. | Do not package caches or repository internals. | true |
| Known limitations | List synthetic-only, toy_lio, failed validity screens, no method update, and small scene-family scope. | reviewer risk transparency | Limitations are part of the diagnostic contribution. | Do not soften No-Go evidence. | true |
