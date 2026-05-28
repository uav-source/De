# Release Cleanup Plan

| cleanup_item | path_or_pattern | current_status | required_action | blocking_for_release | reason |
| --- | --- | --- | --- | --- | --- |
| CLEAN01 | .git | present in repository checkout | exclude from release archive unless sharing git history intentionally | true | release package should not include repository internals |
| CLEAN02 | .pytest_cache | ignored by .gitignore | exclude from final archive | true | cache files are not evidence |
| CLEAN03 | __pycache__ | ignored by .gitignore | exclude from final archive | true | compiled caches are not evidence |
| CLEAN04 | results/day14/raw/*.tum | generated artifact | decide whether to package or rebuild via reproduce_day14.sh | false | raw trajectories can be regenerated |
| CLEAN05 | results/day30/tables/day15-day26*.csv | key evidence tables | force-add or document regeneration route for selected release | true | paper evidence depends on CSV tables |
| CLEAN06 | final archive caches | not cleaned by Day26 | exclude cache directories and font caches | true | prevents noisy release bundles |
| CLEAN07 | README.md | needs scope update | add diagnostic benchmark scope and reproduction commands | true | README is reviewer entry point |
| CLEAN08 | python3 -m pytest -q | confirmed in current run when executed | rerun before final package | true | local quality gate |
| CLEAN09 | smoke vs real plots | documented in plans, not yet README | explain smoke reproduction versus real rendering | true | prevents figure reproducibility confusion |
