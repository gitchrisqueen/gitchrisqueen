# Project write-ups, with numbers and limits

The long form of the four project cards on the [profile](../README.md). Each entry says what the project does, what broke, and where its numbers stop being reliable.

## LinkedIn Engagement Manager (LEM)

Keeping up a LinkedIn presence means a content plan, posts at the right hours, and replies and comments every day. [LEM](https://github.com/christopherqueenconsulting/linkedin_engagement_manager) is a web app (FastAPI, Celery and Redis, MySQL, React, Selenium, LiteLLM, Docker Compose) that builds a 30-day content plan, runs AI-generated posts through quality gates and an optional approval step, and handles engagement under per-user targeting and daily caps. It is live at [lem.christopherqueenconsulting.com](https://lem.christopherqueenconsulting.com/).

What broke: in September 2026 the live app sat on v0.176.5 for about a day while v0.177.0 to v0.178.1 were tagged, and the only trace was a warning inside a green run. Since 2026-09-25 an [hourly check](https://github.com/christopherqueenconsulting/linkedin_engagement_manager/blob/main/.github/workflows/deploy-drift-check.yml) compares the live app's public version with the published releases and opens one issue when a release has waited too long ([#2194](https://github.com/christopherqueenconsulting/linkedin_engagement_manager/pull/2194)).

Limits: deployed and CI-gated (continuous integration: tests run on every change); no revenue.

## CPCC Task Automation (instructor admin tool)

Every week, for each course I teach, I took attendance, recorded withdrawals and graded programming work by hand, and one missed submission is a wrong record. [CPCC Task Automation](https://github.com/christopherqueenconsulting/cpcc_task_automation) (Python, Streamlit, Selenium, LangChain, OpenRouter) drives the student information system and the learning platform through a real browser, grades against a rubric with a human review step, and writes grades back as drafts where the platform allows one, with a dry run as the default.

What broke: the model flagged valid C++ as "does not compile", a major rubric error, and took the whole grade to the floor. The fix was not a better prompt: a [real compiler now decides "does not compile"](https://github.com/christopherqueenconsulting/cpcc_task_automation/blob/master/docs/compiler-gate.md), and student code is compiled, never run (merged 2026-09-02, [#267](https://github.com/christopherqueenconsulting/cpcc_task_automation/pull/267)).

Limits: invite-only, built for instructor admin work; no public demo; I am its only user, for my own courses ([case study](https://christopherqueenconsulting.com/work/cpcc-task-automation/?utm_source=github&utm_medium=readme&utm_campaign=cpcc-task-automation)).

## hearing-copilot: speaker identification

A live transcript is only useful if it says who is talking. [hearing-copilot](https://github.com/gitchrisqueen/hearing-copilot) is a local JavaScript app that transcribes a hearing and labels the speakers. Before speaker identification went into the app, I ran an offline bake-off on real Supreme Court oral-argument audio, with Oyez transcripts as ground truth.

The number ([RESULTS.md](https://github.com/gitchrisqueen/hearing-copilot/blob/main/eval/diarization/RESULTS.md), dated 2026-07-24): in the cold-start run (no voice samples enrolled beforehand) on *Bowe v. United States* (argued 2025-10-14, 91 minutes, 12 speakers), it auto-accepted 89.8% of the chunks (short audio segments) and was right on 99.2% of the chunks it auto-accepted.

Limits: this is one hearing and one cold-start run, clustered and scored on the same 91 minutes with no train and test split, and RESULTS.md gives no chunk counts or confidence interval for the two percentages. The accept threshold (0.65) was chosen from a calibration table over both main runs, so the headline is not held-out; that table lists 91 to 92% coverage at 0.65, a little above the 89.8% headline, and I have not re-derived which threshold produced the headline row. The cold-start numbers use an optimistic greedy cluster-to-speaker mapping; no Zoom-quality audio has been tested; the cold-start chunk total is not reported.

## panthera and lottery-guru: paper trading and a chance experiment

[panthera](https://github.com/gitchrisqueen/panthera) is an automated MLB paper-trading pipeline on GitHub Actions: odds snapshots three times a day, picks from documented rules, graded the next morning, ledger committed to git. Each strategy is pre-registered, meaning its success criteria were written down before the data came in, and [the report](https://github.com/gitchrisqueen/panthera/blob/main/reports/BETTING_REPORT.md) says plainly that at these sample sizes no ROI bar controls both error rates. [lottery-guru](https://github.com/gitchrisqueen/lottery-guru) is a null-hypothesis experiment on lottery-draw prediction: daily predictions from folk strategies plus LLM arms, scored against real draws, with z and p per strategy on [a leaderboard](https://github.com/gitchrisqueen/lottery-guru/blob/main/REPORT.md).

What broke: the repo's own [health-check workflow](https://github.com/gitchrisqueen/panthera/blob/main/.github/workflows/health.yml) records where it came from: the last regular-season pick landed on 2026-09-27, the first all-silent slate was 2026-09-29, and, by the repo's own count, nobody noticed for 14 slate days because every workflow stayed green. The cause was a config whitelist that excluded the MLB postseason, [fixed on 2026-10-15](https://github.com/gitchrisqueen/panthera/commit/1c4619f); the report's later picks, such as 2026-10-19, are postseason ones. A daily health check now scores each finished slate day and opens an issue for a dead one; its run status alone does not show a dead slate.

Limits: panthera is paper trading only, and its ledger is idle outside the MLB season. On the ledger updated 2026-10-23, the one strategy marked supported shows +7.99% ROI over 227 graded picks (124 wins, 103 losses). The 6.7 points in the report is one standard error, not a confidence interval. Its regular-season picks returned +8.59% and its 4 postseason picks -36.90% (too few to read), it overlaps 54% with other strategies' picks, and with several strategies running at once the report expects at least one false-positive screen, so it treats the result as a screen, not proof. lottery-guru's expected result is that every arm converges to chance, and its leaderboard applies no multiple-comparison correction across its many strategies.

Also: [CueSyncAR](https://github.com/gitchrisqueen/CueSyncAR), an iOS augmented-reality billiards prototype in Swift, paused since 2026-09-10.
