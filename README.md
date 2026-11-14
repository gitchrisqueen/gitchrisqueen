<picture>
  <source media="(prefers-reduced-motion: no-preference)" srcset="assets/header-animated.svg">
  <img src="assets/header-static.svg" alt="Christopher Queen, Applied AI / Forward-Deployed Engineer" width="100%">
</picture>

**I build LLM systems with real checks and traceability, aimed at catching problems before customers see them.**

<a href="https://christopherqueenconsulting.com/resume/?utm_source=github&utm_medium=readme&utm_campaign=resume"><img alt="Résumé" src="https://img.shields.io/badge/-R%C3%A9sum%C3%A9-e9d437?style=for-the-badge&labelColor=e9d437"></a>
<a href="https://christopherqueenconsulting.com/work/cpcc-task-automation/?utm_source=github&utm_medium=readme&utm_campaign=cpcc-task-automation"><img alt="Case study: what I caught and how I fixed it" src="https://img.shields.io/badge/-Case%20study-21262d?style=for-the-badge&labelColor=21262d"></a>
<a href="https://christopherqueenconsulting.com/ai-ops-audit/"><img alt="The LLM audit: what you get" src="https://img.shields.io/badge/-LLM%20audit-21262d?style=for-the-badge&labelColor=21262d"></a>
<a href="https://www.linkedin.com/in/christopherqueen"><img alt="LinkedIn" src="https://img.shields.io/badge/-LinkedIn-21262d?style=for-the-badge&logo=linkedin&logoColor=white&labelColor=21262d"></a>
<a href="mailto:christopher.queen@gmail.com"><img alt="Email" src="https://img.shields.io/badge/-Email-21262d?style=for-the-badge&logo=gmail&logoColor=white&labelColor=21262d"></a>

<picture>
  <source media="(prefers-reduced-motion: no-preference)" srcset="assets/terminal-animated.svg">
  <img src="assets/terminal-static.svg" alt="A terminal session with the cqc command line tool: cqc --help lists four commands; cqc mcp connect skills lists six tools (llm_audit, real_check, drift_watch, browser_flow, ci_pipeline, human_gate); cqc call llm_audit --sample prints grades for spend efficiency, reliability, observability, governance and leverage; cqc about prints: Title: Applied AI / FDE. Base: Jacksonville FL, remote. Status: open to FDE roles. Builds LLM systems with real checks. Stack: Python, FastAPI, React. Models: LangChain, LiteLLM. Rule: checks beat prompts." width="776">
</picture>

<sub>The terminal above is <a href="https://github.com/gitchrisqueen/cqc"><code>cqc</code></a>, a small command line tool of AI-reliability checks served as MCP tools. <a href="https://github.com/gitchrisqueen/gitchrisqueen/blob/main/docs/PROOF.md#cqc-the-tool-behind-the-terminal">What each tool is based on</a>.</sub>

<a href="https://gitchrisqueen.github.io/gitchrisqueen/graph/">
<picture>
  <source media="(prefers-reduced-motion: no-preference)" srcset="assets/graph-animated.svg">
  <img src="assets/graph-static.svg" alt="A knowledge graph of what I work with. Christopher connects to four projects (LEM, the CPCC tool, hearing-copilot, panthera) and to the LLM audit. Practices (real checks, drift watch, human review, honest caveats) and tools (Python, FastAPI, Redis, React, Selenium, LangChain, LiteLLM, Docker, GitHub Actions, Node.js) tie them together. Select it to open the interactive version, where you can drag the nodes." width="776">
</picture>
</a>

<sub>Gold dots are projects, green dots are practices, logos are tools. Select the graph to open the interactive version and drag the nodes.</sub>

## What I've built

<a href="https://github.com/christopherqueenconsulting/linkedin_engagement_manager"><img alt="LinkedIn Engagement Manager. A LinkedIn content and engagement app. At stake: The live app sat on an old release for a day, and nobody told. What I did: Safe database changes ship on their own; risky ones hold and alert me. Of 134 past changes, 102 would ship on their own. Sound familiar? Has a release sat unshipped because a gate held it and no one told you? Built with FastAPI, Celery, Redis, MySQL, React and Docker." src="assets/card-lem.svg" width="386"></a>
<a href="https://github.com/christopherqueenconsulting/cpcc_task_automation"><img alt="CPCC Task Automation. Grading and admin tool for my own courses. At stake: One false &quot;does not compile&quot; verdict floored a submission's whole grade. What I did: A real compiler now overrules the model. &quot;Can't verify&quot; never counts as a fail; the compile check never runs student code. Sound familiar? Does an AI verdict in your workflow ever count with no hard check behind it? Built with Python, Streamlit, Selenium and LangChain." src="assets/card-cpcc.svg" width="386"></a>
<a href="https://github.com/gitchrisqueen/hearing-copilot"><img alt="hearing-copilot. Names the speakers in a hearing transcript. At stake: A wrong speaker name pins words on the wrong person. What I did: Scored 91 min of real court audio first: 99.2% right on the 89.8% it auto-accepted. One hearing, not held out, no interval. Sound familiar? Does your AI guess who said what, with nobody checking the guesses? Built with JavaScript and Node.js." src="assets/card-hearing.svg" width="386"></a>
<a href="https://github.com/gitchrisqueen/panthera"><img alt="panthera. An MLB prediction pipeline, no real money. At stake: Scheduled runs produced no picks for 14 slate days, and every run showed green. What I did: Fixed the cause; a daily health check now flags a no-picks slate about a day later. I also won't call +7.99% an edge: it is about 1.2 standard errors from zero. Sound familiar? Do your scheduled jobs ever run green for weeks while quietly producing nothing? Built with Python and GitHub Actions." src="assets/card-panthera.svg" width="386"></a>

Test status, live: <a href="https://github.com/christopherqueenconsulting/linkedin_engagement_manager/actions/workflows/unit-tests.yml"><img alt="LinkedIn Engagement Manager automated tests status" src="https://img.shields.io/github/actions/workflow/status/christopherqueenconsulting/linkedin_engagement_manager/unit-tests.yml?branch=main&label=LEM&labelColor=24292f&color=57606a&style=flat-square"></a>
<a href="https://github.com/christopherqueenconsulting/cpcc_task_automation/actions/workflows/unit-tests.yml"><img alt="CPCC Task Automation automated tests status" src="https://img.shields.io/github/actions/workflow/status/christopherqueenconsulting/cpcc_task_automation/unit-tests.yml?branch=master&label=CPCC&labelColor=24292f&color=57606a&style=flat-square"></a>
<a href="https://github.com/gitchrisqueen/hearing-copilot/actions/workflows/ci.yml"><img alt="hearing-copilot automated tests and lint status" src="https://img.shields.io/github/actions/workflow/status/gitchrisqueen/hearing-copilot/ci.yml?branch=main&label=hearing-copilot&labelColor=24292f&color=57606a&style=flat-square"></a>
<a href="https://github.com/gitchrisqueen/panthera/actions/workflows/mvp-morning.yml"><img alt="panthera daily pipeline run status" src="https://img.shields.io/github/actions/workflow/status/gitchrisqueen/panthera/mvp-morning.yml?branch=main&label=panthera%20daily%20run&labelColor=24292f&color=57606a&style=flat-square"></a>

More: [the LEM live app](https://lem.christopherqueenconsulting.com/), [the CPCC case study](https://christopherqueenconsulting.com/work/cpcc-task-automation/?utm_source=github&utm_medium=readme&utm_campaign=cpcc-task-automation), [hearing-copilot results and caveats](https://github.com/gitchrisqueen/hearing-copilot/blob/main/eval/diarization/RESULTS.md), [the panthera report](https://github.com/gitchrisqueen/panthera/blob/main/reports/BETTING_REPORT.md), and [cqc](https://github.com/gitchrisqueen/cqc), the tool behind the terminal above, and [every number with its caveats](https://github.com/gitchrisqueen/gitchrisqueen/blob/main/docs/PROOF.md). Also [CueSyncAR](https://github.com/gitchrisqueen/CueSyncAR), an iOS augmented-reality billiards prototype in Swift, declared paused on 2026-09-10.

<details>
<summary><img src="assets/pill-status.svg" alt="Live status of the four checks (select to open)" width="520"></summary>

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

<img src="assets/skills-build.svg" alt="Languages and services used in the projects above: Python, JavaScript, Swift, Node.js, FastAPI, Celery, Redis and MySQL." width="386"><img src="assets/skills-ai.svg" alt="AI, interface, test and ship tools used in the projects above: LangChain, LiteLLM, OpenRouter, React, Streamlit, Selenium, Docker and GitHub Actions." width="386">

## Merged into other people's projects

<details>
<summary><img src="assets/pill-merged.svg" alt="Merged pull requests in other people's projects (select to open)" width="520"></summary>

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
<summary><img src="assets/pill-hire.svg" alt="Hire me, or book the audit (select to open)" width="520"></summary>

**Hiring:** I start from the job someone still does by hand, write down the boundary before building, put a real check where the model is weakest, and leave a [hand-off document](https://github.com/christopherqueenconsulting/cpcc_task_automation/blob/master/docs/BRIGHTSPACE_AUTOMATION_HANDOFF.md) the next engineer can run from.

**The audit:** one week, read-only access to your LLM logs and bills, a graded scorecard and a costed fix list. [See what you get](https://christopherqueenconsulting.com/ai-ops-audit/). [Book a free 30-minute call](https://christopherqueenconsulting.com/schedule/).
</details>

I build with AI coding agents in the loop; the upstream pull requests below were written that way too.

## At a glance

**Christopher Queen**, Applied AI and Forward-Deployed Engineer in Jacksonville, FL (remote). Open to Forward-Deployed Engineer roles. I also run a one-week LLM spend and reliability audit.

**Skills:** Python, JavaScript and Node.js, Swift; FastAPI, Celery, Redis, MySQL, React, Streamlit; LLM systems with LangChain, LiteLLM, OpenRouter and MCP; evals and real checks; observability with PostHog; browser automation with Selenium; Docker and GitHub Actions.

**Projects:** [LinkedIn Engagement Manager](https://github.com/christopherqueenconsulting/linkedin_engagement_manager) ships safe database changes automatically and holds risky ones. [CPCC Task Automation](https://github.com/christopherqueenconsulting/cpcc_task_automation) lets a real compiler overrule the model. [hearing-copilot](https://github.com/gitchrisqueen/hearing-copilot) labels speakers, scored on real court audio. [panthera](https://github.com/gitchrisqueen/panthera) is a prediction pipeline with a daily health check. [cqc](https://github.com/gitchrisqueen/cqc) is the command line tool behind the terminal above.

**Open source:** merged pull requests in LangChain, PostHog, lossless-claw, google_workspace_mcp and future-agi.

**Contact:** [LinkedIn](https://www.linkedin.com/in/christopherqueen), christopher.queen@gmail.com, [christopherqueenconsulting.com](https://christopherqueenconsulting.com).

## Contribution calendar

<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="https://raw.githubusercontent.com/gitchrisqueen/gitchrisqueen/output/snake-static-dark.svg">
  <img alt="Contribution calendar for the past year, drawn as a snake that eats each active day." src="https://raw.githubusercontent.com/gitchrisqueen/gitchrisqueen/output/snake-dark.svg" width="776">
</picture>

The snake grows a little with each active day it eats.

For AI assistants: https://christopherqueenconsulting.com/for-agents/

<picture>
  <source media="(prefers-reduced-motion: no-preference)" srcset="assets/footer-animated.svg">
  <img src="assets/footer-static.svg" alt="Jacksonville, FL. Remote. Open to Forward-Deployed Engineer roles. christopherqueenconsulting.com" width="100%">
</picture>

<small>The sections between HTML comment markers are regenerated from public GitHub data by a scheduled check in this repo; the rest is written by hand.</small>
