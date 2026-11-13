<picture>
  <source media="(prefers-reduced-motion: no-preference)" srcset="assets/header-animated.svg">
  <img src="assets/header-static.svg" alt="" width="100%">
</picture>

# Christopher Queen

**Applied AI / Forward-Deployed Engineer**, which means I work inside your team to build large language model (LLM) systems that are tested, measured and deployed, and I write down what broke. If an LLM bill or error rate is your problem, I also run a fixed-price audit. None of the systems below has an outside paying customer yet, and the audit has not been sold yet. Most of this work was written with AI coding agents.

[Résumé (remote, Jacksonville FL)](https://www.christopherqueenconsulting.com/resume/?utm_source=github&utm_medium=readme&utm_campaign=resume) · [Case study: what broke and what I changed](https://www.christopherqueenconsulting.com/work/cpcc-task-automation/?utm_source=github&utm_medium=readme&utm_campaign=cpcc-task-automation) · [Audit: what you get](https://christopherqueenconsulting.com/ai-ops-audit/)

[![LinkedIn Engagement Manager automated tests status](https://img.shields.io/github/actions/workflow/status/christopherqueenconsulting/linkedin_engagement_manager/unit-tests.yml?branch=main&label=LinkedIn%20Engagement%20Manager%3A%20automated%20tests&labelColor=24292f&color=57606a)](https://github.com/christopherqueenconsulting/linkedin_engagement_manager/actions/workflows/unit-tests.yml)
[![Instructor admin tool automated tests status](https://img.shields.io/github/actions/workflow/status/christopherqueenconsulting/cpcc_task_automation/unit-tests.yml?branch=master&label=Instructor%20admin%20tool%3A%20automated%20tests&labelColor=24292f&color=57606a)](https://github.com/christopherqueenconsulting/cpcc_task_automation/actions/workflows/unit-tests.yml)
[![MLB paper-trading experiment daily check status](https://img.shields.io/github/actions/workflow/status/gitchrisqueen/panthera/mvp-morning.yml?branch=main&label=MLB%20paper-trading%20experiment%3A%20daily%20check&labelColor=24292f&color=57606a)](https://github.com/gitchrisqueen/panthera/actions/workflows/mvp-morning.yml)

## What I've built

### LinkedIn Engagement Manager (LEM)

Keeping up a LinkedIn presence means a content plan, posts at the right hours, and replies and comments every day. [LEM](https://github.com/christopherqueenconsulting/linkedin_engagement_manager) is a web app (FastAPI, Celery and Redis, MySQL, React, Selenium, LiteLLM, Docker Compose) that builds a 30-day content plan, runs AI-generated posts through quality gates and an optional approval step, and handles engagement under per-user targeting and daily caps. It is live at [lem.christopherqueenconsulting.com](https://lem.christopherqueenconsulting.com/).

What broke: in September 2026 the live app sat on v0.176.5 for about a day while v0.177.0 to v0.178.1 were tagged, and the only trace was a warning inside a green run. Since 2026-09-25 an [hourly check](https://github.com/christopherqueenconsulting/linkedin_engagement_manager/blob/main/.github/workflows/deploy-drift-check.yml) compares the live app's public version with the published releases and opens one issue when a release has waited too long ([#2194](https://github.com/christopherqueenconsulting/linkedin_engagement_manager/pull/2194)).

Limits: deployed and CI-gated (continuous integration: tests run on every change); no revenue.

### CPCC Task Automation (instructor admin tool)

Every week, for each course I teach, I took attendance, recorded withdrawals and graded programming work by hand, and one missed submission is a wrong record. [This tool](https://github.com/christopherqueenconsulting/cpcc_task_automation) (Python, Streamlit, Selenium, LangChain, OpenRouter) drives the student information system and the learning platform through a real browser, grades against a rubric with a human review step, and writes grades back as drafts where the platform allows one, with a dry run as the default.

What broke: the model flagged valid C++ as "does not compile", a major rubric error, and took the whole grade to the floor. The fix was not a better prompt: a [real compiler now decides "does not compile"](https://github.com/christopherqueenconsulting/cpcc_task_automation/blob/master/docs/compiler-gate.md), and student code is compiled, never run (merged 2026-09-02, [#267](https://github.com/christopherqueenconsulting/cpcc_task_automation/pull/267)).

Limits: invite-only, built for instructor admin work; no public demo; I am its only user, for my own courses ([case study](https://www.christopherqueenconsulting.com/work/cpcc-task-automation/?utm_source=github&utm_medium=readme&utm_campaign=cpcc-task-automation)).

### hearing-copilot: speaker identification

A live transcript is only useful if it says who is talking. [hearing-copilot](https://github.com/gitchrisqueen/hearing-copilot) is a local app that transcribes a hearing and labels the speakers. Before speaker identification went into the app, I ran an offline bake-off on real Supreme Court oral-argument audio, with Oyez transcripts as ground truth.

The number ([RESULTS.md](https://github.com/gitchrisqueen/hearing-copilot/blob/main/eval/diarization/RESULTS.md), dated 2026-07-24): in the cold-start run (no voice samples enrolled beforehand) on *Bowe v. United States* (argued 2025-10-14, 91 minutes, 12 speakers), it auto-accepted 89.8% of the chunks (short audio segments) and was right on 99.2% of the chunks it auto-accepted.

Limits: the accept threshold (0.65) was chosen from a calibration table over the same two main runs it is reported on (enrolled and cold-start), so the headline is not held-out; the cold-start numbers use an optimistic greedy cluster-to-speaker mapping; no Zoom-quality audio has been tested; the cold-start chunk total is not reported.

### panthera and lottery-guru: paper trading and a chance experiment

[panthera](https://github.com/gitchrisqueen/panthera) is an automated MLB paper-trading pipeline on GitHub Actions: odds snapshots three times a day, picks from documented rules, graded the next morning, ledger committed to git. Each strategy is pre-registered, meaning its success criteria were written down before the data came in, and [the report](https://github.com/gitchrisqueen/panthera/blob/main/reports/BETTING_REPORT.md) says plainly that at these sample sizes no ROI bar controls both error rates. [lottery-guru](https://github.com/gitchrisqueen/lottery-guru) is a null-hypothesis experiment on lottery-draw prediction: daily predictions from folk strategies plus LLM arms, scored against real draws, with z and p per strategy on [a leaderboard](https://github.com/gitchrisqueen/lottery-guru/blob/main/REPORT.md).

What broke: panthera's last MLB pick landed on 2026-09-27, slates went silent from 2026-09-29, and nobody noticed for 14 slate days, because every workflow stayed green. A [daily health check](https://github.com/gitchrisqueen/panthera/blob/main/.github/workflows/health.yml) now scores each finished slate day and reports a dead one.

Limits: panthera is paper trading only. On the ledger updated 2026-10-23, the one strategy marked supported shows +7.99% ROI (±6.7 points) over 227 graded picks, and the report treats that as a screen, not proof. lottery-guru's expected result is that every arm converges to chance.

Also: [CueSyncAR](https://github.com/gitchrisqueen/CueSyncAR), an iOS augmented-reality billiards prototype in Swift, paused since 2026-09-10.

## Status of the flagship repos

This table covers the four projects above and is the readable version of the badges at the top. Passing means the last run of that check on the default branch succeeded, failing means it did not, and unavailable means the run could not be read. A failing row stays visible.

<!-- FLAGSHIPS:START -->
| Repo | Check | Status |
|---|---|---|
| [christopherqueenconsulting/linkedin_engagement_manager](https://github.com/christopherqueenconsulting/linkedin_engagement_manager) | automated tests | passing |
| [christopherqueenconsulting/cpcc_task_automation](https://github.com/christopherqueenconsulting/cpcc_task_automation) | automated tests | passing |
| [gitchrisqueen/hearing-copilot](https://github.com/gitchrisqueen/hearing-copilot) | automated tests | passing |
| [gitchrisqueen/panthera](https://github.com/gitchrisqueen/panthera) | daily check | passing |
<!-- FLAGSHIPS:END -->

## Merged into other people's projects

Mostly small fixes, merged by each project's maintainers. The list is generated from public GitHub data by a scheduled check in this repo. Most of this work was written with AI coding agents.

<!-- MERGED-UPSTREAM:START -->
- [future-agi/future-agi #1327](https://github.com/future-agi/future-agi/pull/1327): added scrolling to the eval log explanation panel
- [PostHog/posthog-openclaw #35](https://github.com/PostHog/posthog-openclaw/pull/35): falls back to an environment variable for the PostHog host URL
- [Martian-Engineering/lossless-claw #418](https://github.com/Martian-Engineering/lossless-claw/pull/418): fixed manual compaction finishing under its target size
- [PostHog/posthog-openclaw #15](https://github.com/PostHog/posthog-openclaw/pull/15): API key environment-variable fallback, schema caching and a clearer missing-key warning
- [taylorwilsdon/google_workspace_mcp #644](https://github.com/taylorwilsdon/google_workspace_mcp/pull/644): defaults the single-user email to an environment variable
- [langchain-ai/langchain #15251](https://github.com/langchain-ai/langchain/pull/15251): fixed the .devcontainer build
<!-- MERGED-UPSTREAM:END -->

Closed without merge, a sample, 6 of 14: LangChain agent tool-input parser fix ([#14668](https://github.com/langchain-ai/langchain/pull/14668), [#15422](https://github.com/langchain-ai/langchain/pull/15422)); mem0 session-memory scoping, provider environment variables and a hook migration ([#4574](https://github.com/mem0ai/mem0/pull/4574), [#4987](https://github.com/mem0ai/mem0/pull/4987), [#5077](https://github.com/mem0ai/mem0/pull/5077)); Lossless-Claw SQLite busy timeout ([#303](https://github.com/Martian-Engineering/lossless-claw/pull/303)). [Full list on GitHub](https://github.com/search?q=is%3Apr+is%3Aclosed+is%3Aunmerged+author%3Agitchrisqueen+-user%3Agitchrisqueen+-org%3Achristopherqueenconsulting&type=pullrequests).

## Hire me, or have me audit your LLM system

**Hiring.** I work remote from Jacksonville, FL, and travel is fine. I start from the job someone still does by hand, write down the boundary before building, put a real check where the model is weakest (the compiler gate above), and leave a [hand-off document](https://github.com/christopherqueenconsulting/cpcc_task_automation/blob/master/docs/BRIGHTSPACE_AUTOMATION_HANDOFF.md) the next engineer can run from. [Résumé](https://www.christopherqueenconsulting.com/resume/?utm_source=github&utm_medium=readme&utm_campaign=resume).

**Running an LLM system.** The audit takes one week. With read-only access to your LLM call logs and bills, I trace where the spend goes and where calls fail, grade five areas from A to F (spend efficiency, reliability, observability, governance, and the work still done by hand), and hand over an 8 to 12 page report with a costed fix list, then walk through it with you on a readout call. [What you get](https://christopherqueenconsulting.com/ai-ops-audit/).

## Tools I use

[Python](https://github.com/christopherqueenconsulting/cpcc_task_automation), [FastAPI](https://github.com/christopherqueenconsulting/linkedin_engagement_manager), [Celery and Redis](https://github.com/christopherqueenconsulting/linkedin_engagement_manager), [React](https://github.com/christopherqueenconsulting/linkedin_engagement_manager), [LiteLLM](https://github.com/christopherqueenconsulting/linkedin_engagement_manager), [Docker Compose](https://github.com/christopherqueenconsulting/linkedin_engagement_manager), [Streamlit](https://github.com/christopherqueenconsulting/cpcc_task_automation), [Selenium](https://github.com/christopherqueenconsulting/cpcc_task_automation), [LangChain](https://github.com/christopherqueenconsulting/cpcc_task_automation), [OpenRouter](https://github.com/christopherqueenconsulting/cpcc_task_automation), [JavaScript on Node](https://github.com/gitchrisqueen/hearing-copilot), [GitHub Actions](https://github.com/gitchrisqueen/panthera), [Swift](https://github.com/gitchrisqueen/CueSyncAR).

## Off the keyboard

Reader, billiards player, and aquarist (yes, I keep the tanks alive too).

## Connect

- LinkedIn: [linkedin.com/in/christopherqueen](https://www.linkedin.com/in/christopherqueen)
- Email: christopher.queen@gmail.com
- Consulting: [Christopher Queen Consulting](https://christopherqueenconsulting.com)

## Contribution calendar

<picture>
  <source media="(prefers-reduced-motion: reduce) and (prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/gitchrisqueen/gitchrisqueen/output/snake-static-dark.svg">
  <source media="(prefers-reduced-motion: reduce)" srcset="https://raw.githubusercontent.com/gitchrisqueen/gitchrisqueen/output/snake-static-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/gitchrisqueen/gitchrisqueen/output/snake-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/gitchrisqueen/gitchrisqueen/output/snake.svg">
  <img alt="Contribution calendar for the past year" src="https://raw.githubusercontent.com/gitchrisqueen/gitchrisqueen/output/snake-static-light.svg">
</picture>

Calendar includes private work. Most of this work was written with AI coding agents.

<picture>
  <source media="(prefers-reduced-motion: no-preference)" srcset="assets/footer-animated.svg">
  <img src="assets/footer-static.svg" alt="" width="100%">
</picture>

<sub>The sections between HTML comment markers are regenerated from public GitHub data by a scheduled check in this repo; the rest is written by hand.</sub>
