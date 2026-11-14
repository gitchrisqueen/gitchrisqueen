<picture>
  <source media="(prefers-reduced-motion: no-preference)" srcset="assets/header-animated.svg">
  <img src="assets/header-static.svg" alt="Christopher Queen, Applied AI / Forward-Deployed Engineer" width="100%">
</picture>

**I build LLM systems with real checks around the model, ship them, and write down what broke.**

<a href="https://christopherqueenconsulting.com/resume/?utm_source=github&utm_medium=readme&utm_campaign=resume"><img alt="Résumé" src="https://img.shields.io/badge/-R%C3%A9sum%C3%A9-e9d437?style=for-the-badge&labelColor=e9d437"></a>
<a href="https://christopherqueenconsulting.com/work/cpcc-task-automation/?utm_source=github&utm_medium=readme&utm_campaign=cpcc-task-automation"><img alt="Case study: what broke and what I changed" src="https://img.shields.io/badge/-Case%20study-21262d?style=for-the-badge&labelColor=21262d"></a>
<a href="https://christopherqueenconsulting.com/ai-ops-audit/"><img alt="The LLM audit: what you get" src="https://img.shields.io/badge/-LLM%20audit-21262d?style=for-the-badge&labelColor=21262d"></a>
<a href="https://www.linkedin.com/in/christopherqueen"><img alt="LinkedIn" src="https://img.shields.io/badge/-LinkedIn-21262d?style=for-the-badge&logo=linkedin&logoColor=white&labelColor=21262d"></a>
<a href="mailto:christopher.queen@gmail.com"><img alt="Email" src="https://img.shields.io/badge/-Email-21262d?style=for-the-badge&logo=gmail&logoColor=white&labelColor=21262d"></a>

<picture>
  <source media="(prefers-reduced-motion: no-preference)" srcset="assets/neofetch-animated.svg">
  <img src="assets/neofetch-static.svg" alt="About me as a terminal readout. Title: Applied AI, Forward-Deployed Engineer. Base: Jacksonville, Florida, remote. Status: open to Forward-Deployed Engineer roles. Builds LLM systems with real checks. Stack: Python, FastAPI, React, Docker. Models: LangChain, LiteLLM, OpenRouter. Rule: a real check beats a prompt. Off duty: books, billiards, aquariums." width="100%">
</picture>

<picture>
  <source media="(prefers-reduced-motion: no-preference)" srcset="assets/loop-animated.svg">
  <img src="assets/loop-static.svg" alt="My automation loop: ingest, language model, tool call, evaluation, human approval, ship. A real check and a person sit between the model and the world." width="100%">
</picture>

## What I've built

<a href="https://github.com/christopherqueenconsulting/linkedin_engagement_manager"><img alt="LinkedIn Engagement Manager, a live web app: a 30-day content plan, quality-gated AI posts and daily-capped engagement. What broke: the live app sat behind new releases for a day, inside a green run; an hourly check now flags it. Built with FastAPI, Celery, Redis, MySQL, React and Docker." src="assets/card-lem.svg" width="390"></a>
<a href="https://github.com/christopherqueenconsulting/cpcc_task_automation"><img alt="CPCC Task Automation, an instructor admin tool: attendance, withdrawals and rubric grading with a human review step. What broke: the model called valid C++ not compiling; a real compiler now makes that call. Built with Python, Streamlit, Selenium and LangChain." src="assets/card-cpcc.svg" width="390"></a>
<a href="https://github.com/gitchrisqueen/hearing-copilot"><img alt="hearing-copilot, speaker identification for live transcripts, scored offline on real oral-argument audio. Limits: the headline score comes from one hearing, with no confidence interval; caveats are in RESULTS.md. Built with JavaScript and Node.js." src="assets/card-hearing.svg" width="390"></a>
<a href="https://github.com/gitchrisqueen/panthera"><img alt="panthera, an MLB paper-trading experiment graded against pre-registered rules; paper trading only, and the ROI is a screen, not proof. What broke: a config whitelist skipped the postseason and 14 slate days passed unnoticed; a health check now flags it. Built with Python and GitHub Actions." src="assets/card-panthera.svg" width="390"></a>

Test status, live: <a href="https://github.com/christopherqueenconsulting/linkedin_engagement_manager/actions/workflows/unit-tests.yml"><img alt="LinkedIn Engagement Manager automated tests status" src="https://img.shields.io/github/actions/workflow/status/christopherqueenconsulting/linkedin_engagement_manager/unit-tests.yml?branch=main&label=LEM&labelColor=24292f&color=57606a&style=flat-square"></a>
<a href="https://github.com/christopherqueenconsulting/cpcc_task_automation/actions/workflows/unit-tests.yml"><img alt="CPCC Task Automation automated tests status" src="https://img.shields.io/github/actions/workflow/status/christopherqueenconsulting/cpcc_task_automation/unit-tests.yml?branch=master&label=CPCC&labelColor=24292f&color=57606a&style=flat-square"></a>
<a href="https://github.com/gitchrisqueen/hearing-copilot/actions/workflows/ci.yml"><img alt="hearing-copilot automated tests and lint status" src="https://img.shields.io/github/actions/workflow/status/gitchrisqueen/hearing-copilot/ci.yml?branch=main&label=hearing-copilot&labelColor=24292f&color=57606a&style=flat-square"></a>
<a href="https://github.com/gitchrisqueen/panthera/actions/workflows/mvp-morning.yml"><img alt="panthera daily pipeline run status" src="https://img.shields.io/github/actions/workflow/status/gitchrisqueen/panthera/mvp-morning.yml?branch=main&label=panthera%20daily%20run&labelColor=24292f&color=57606a&style=flat-square"></a>

More: [the LEM live app](https://lem.christopherqueenconsulting.com/), [the CPCC case study](https://christopherqueenconsulting.com/work/cpcc-task-automation/?utm_source=github&utm_medium=readme&utm_campaign=cpcc-task-automation), [hearing-copilot results and caveats](https://github.com/gitchrisqueen/hearing-copilot/blob/main/eval/diarization/RESULTS.md), [the panthera report](https://github.com/gitchrisqueen/panthera/blob/main/reports/BETTING_REPORT.md), and [every number with its caveats](https://github.com/gitchrisqueen/gitchrisqueen/blob/main/docs/PROOF.md). Also [CueSyncAR](https://github.com/gitchrisqueen/CueSyncAR), an iOS augmented-reality billiards prototype in Swift, declared paused on 2026-09-10.

<details>
<summary>Live status of the four checks (generated from GitHub Actions)</summary>

<!-- FLAGSHIPS:START -->
| Repo | Check | Status |
| --- | --- | --- |
| [LinkedIn Engagement Manager](https://github.com/christopherqueenconsulting/linkedin_engagement_manager) | Automated unit tests | passing |
| [CPCC Task Automation](https://github.com/christopherqueenconsulting/cpcc_task_automation) | Automated unit tests | passing |
| [hearing-copilot](https://github.com/gitchrisqueen/hearing-copilot) | Automated tests and lint | passing |
| [panthera](https://github.com/gitchrisqueen/panthera) | Daily pipeline run | passing |
<!-- FLAGSHIPS:END -->

For panthera, passing means the daily pipeline ran, not that its data is healthy; a separate health check opens an issue for a dead slate.
</details>

## Tools

<img src="assets/skills-build.svg" alt="Languages and services used in the projects above: Python, JavaScript, Swift, Node.js, FastAPI, Celery, Redis and MySQL." width="390">
<img src="assets/skills-ai.svg" alt="AI, interface, test and ship tools used in the projects above: LangChain, LiteLLM, OpenRouter, React, Streamlit, Selenium, Docker and GitHub Actions." width="390">

## Merged into other people's projects

<details>
<summary><code>$ git log --merged upstream</code> (click to open)</summary>

Small fixes, merged by each project's maintainers. Generated from public GitHub data by a scheduled check in this repo.

<!-- MERGED-UPSTREAM:START -->
- [future-agi/future-agi #1327](https://github.com/future-agi/future-agi/pull/1327): Makes the eval log's explanation panel scroll, so long explanations are not cut off (issue 1071)
- [PostHog/posthog-openclaw #35](https://github.com/PostHog/posthog-openclaw/pull/35): Reads the PostHog host URL from an environment variable when the config has none, and a blank host now uses the default
- [PostHog/posthog-openclaw #15](https://github.com/PostHog/posthog-openclaw/pull/15): Reads the PostHog API key from an environment variable when the config has none, caches the schema and warns clearly when the key is missing
- [Martian-Engineering/lossless-claw #418](https://github.com/Martian-Engineering/lossless-claw/pull/418): Makes manual compaction report success when the context is already under the token target
- [taylorwilsdon/google_workspace_mcp #644](https://github.com/taylorwilsdon/google_workspace_mcp/pull/644): Reads the Google account from an environment variable in single-user mode, so tool calls need not pass it
- [langchain-ai/langchain #15251](https://github.com/langchain-ai/langchain/pull/15251): Fixes the dev container build by copying the core and community libraries in the Dockerfile (issue 14631)
<!-- MERGED-UPSTREAM:END -->

My pull requests that were closed without merge are listed too: [full list on GitHub](https://github.com/search?q=is%3Apr+is%3Aclosed+is%3Aunmerged+author%3Agitchrisqueen+-user%3Agitchrisqueen+-org%3Achristopherqueenconsulting&type=pullrequests).
</details>

## Hire me, or have me audit your LLM system

<details>
<summary><code>$ sudo hire-me</code> (no password needed)</summary>

**Hiring:** I start from the job someone still does by hand, write down the boundary before building, put a real check where the model is weakest, and leave a [hand-off document](https://github.com/christopherqueenconsulting/cpcc_task_automation/blob/master/docs/BRIGHTSPACE_AUTOMATION_HANDOFF.md) the next engineer can run from.

**The audit:** one week, read-only access to your LLM logs and bills, a graded scorecard and a costed fix list. [See what you get](https://christopherqueenconsulting.com/ai-ops-audit/). [Book a free 30-minute call](https://christopherqueenconsulting.com/schedule/).
</details>

Straight talk: none of this has an outside paying customer yet, the audit has not been sold yet, and most of the work here, including the upstream pull requests, was written with AI coding agents.

## Contribution calendar

<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="https://raw.githubusercontent.com/gitchrisqueen/gitchrisqueen/output/snake-static-dark.svg">
  <img alt="Contribution calendar for the past year, drawn as a snake that eats each active day." src="https://raw.githubusercontent.com/gitchrisqueen/gitchrisqueen/output/snake-dark.svg" width="100%">
</picture>

The snake grows a little with each active day it eats.

LinkedIn: [linkedin.com/in/christopherqueen](https://www.linkedin.com/in/christopherqueen) · Email: christopher.queen@gmail.com · Consulting: [Christopher Queen Consulting](https://christopherqueenconsulting.com)

For AI assistants: https://christopherqueenconsulting.com/for-agents/

<picture>
  <source media="(prefers-reduced-motion: no-preference)" srcset="assets/footer-animated.svg">
  <img src="assets/footer-static.svg" alt="" width="100%">
</picture>

<small>The sections between HTML comment markers are regenerated from public GitHub data by a scheduled check in this repo; the rest is written by hand.</small>
