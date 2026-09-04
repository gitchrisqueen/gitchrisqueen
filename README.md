# Applied AI Engineer / Forward Deployed Engineer

**I take an ambiguous problem to a running, evaluated system in production, then hand it off.**

15+ years shipping production software (Python, TypeScript/Node, AWS), now building and operating LLM systems in production. I work the way a forward-deployed engineer does: embed with the customer team, turn an ambiguous brief into a running system, and own it end-to-end, from discovery through build, deploy, and proof.

```text
Python · TypeScript/Node · AWS · LLMs · Agents · Agentic systems · Evals · MCP · RAG · Real-time systems
```

---

## 🔨 What I've shipped

- **[CPCC Task Automation](https://github.com/christopherqueenconsulting/cpcc_task_automation)** — my flagship applied-AI build. Streamlit · LangChain · OpenRouter (swappable model allowlist) · Selenium. Automates instructor admin work — attendance, withdrawals, feedback, rubric grading — against a live SIS and LMS, with a human review step, draft-only write-back where the LMS allows one, and a real compiler (not the model) deciding whether student code compiles. 79 test files under `tests/` (counted on `origin/master` at `5d9ef4e`, 2026-09-04). Latest: a real-compiler gate for "does not compile" and BrightSpace draft write-back (#267); withdrawals split out of attendance (#280). [▶ Live app](https://cpcc-task-automation.streamlit.app/) (invite-only).
- **[LinkedIn Engagement Manager](https://github.com/christopherqueenconsulting/linkedin_engagement_manager)** (MIT) — a live SaaS (v0.173.5 as of 2026-09-04): FastAPI · Celery/Redis · MySQL · React · Selenium · LiteLLM · PostHog, Docker Compose on a VPS. 30-day content plans, engagement automation, per-user targeting and caps, Stripe billing, an agent pipeline running under its own GitHub App identity. Live at [lem.christopherqueenconsulting.com](https://lem.christopherqueenconsulting.com/).
- **[duvo](https://github.com/gitchrisqueen/duvo)** — a recorded one-hour forward-deployed-engineer technical exercise, then hardened. A tool server an LLM agent calls on behalf of a business user, exposed over MCP. Three tools that accept identifiers only; every business rule and every calculation is deterministic Python on the server, never the model. Correlation id on every response, a plain-English audit trail, and a script that runs every documented command so the docs cannot claim what did not run. 183 tests, 80% coverage per the repo's auto-written status table.
- **[copilot-core](https://github.com/gitchrisqueen/copilot-core)** → **[hearing-copilot](https://github.com/gitchrisqueen/hearing-copilot)** — two local-first real-time copilot apps had re-converged on the same transcription, speaker-ID, and LLM-failover plumbing, so I extracted it once: no build step, no runtime deps in the core path. Speaker-ID went through an offline bake-off on real SCOTUS oral-argument audio (Oyez transcripts as ground truth) before it touched the app — 99.2% accuracy on auto-accepted chunks from a cold start over a 91-minute, 12-speaker argument.
- **A LiteLLM complexity router** — a pre-call hook that classifies each request and routes it to a model tier. I built and operate one in front of my own tooling; the dated log of model demotions, driven by production tool-call audits, is public: [the router log](https://work.christopherqueenconsulting.com/router-log.html?utm_source=github&utm_medium=readme&utm_campaign=litellm-router).
- **[panthera](https://github.com/gitchrisqueen/panthera)** — an automated MLB paper-trading pipeline on GitHub Actions: three odds snapshots a day, picks from documented rules, graded the next morning, ledger committed to git. Verdict criteria are pre-registered, and the report says plainly that at these sample sizes no ROI bar controls both error rates.
- **[CueSyncAR](https://github.com/gitchrisqueen/CueSyncAR)** — an iOS AR billiards prototype rebuilt on Swift 6.1 / SwiftPM: ten packages, a generated Xcode project, 27 test files, and a roadmap written so parallel agents can claim tasks without colliding.
- **[lottery-guru](https://github.com/gitchrisqueen/lottery-guru)** (MIT, public since 2026-09-03) — an honest null-hypothesis experiment: daily predictions from a portfolio of folk strategies plus LLM arms, scored against real drawings, with z and p per strategy on a leaderboard. The expected result is that every arm converges to chance.

Also: private research tooling on the Claude Agent SDK and Claude Code, not linkable.

## 📝 Case studies

- [CPCC Task Automation](https://www.christopherqueenconsulting.com/work/cpcc-task-automation/?utm_source=github&utm_medium=readme&utm_campaign=cpcc-task-automation) — the flagship, with what broke, the trade-offs, the evaluation, and the hand-off document.
- [Open-source contributions](https://www.christopherqueenconsulting.com/work/open-source/?utm_source=github&utm_medium=readme&utm_campaign=open-source) — the merged-PR ledger, with the maintainer's response on each.
- [LiteLLM complexity router](https://www.christopherqueenconsulting.com/work/litellm-router/?utm_source=github&utm_medium=readme&utm_campaign=litellm-router) — the tiering hook and the log of every model I stopped trusting.

## 🧩 Open-source contributions

Merged upstream:

- **PostHog** — [posthog-openclaw #35](https://github.com/PostHog/posthog-openclaw/pull/35) and [#15](https://github.com/PostHog/posthog-openclaw/pull/15): env-var fallbacks for host and API key, schema caching, clearer missing-key warnings.
- **Lossless-Claw** (Martian Engineering) — [#418](https://github.com/Martian-Engineering/lossless-claw/pull/418): fix for manual compaction landing under target.
- **Google Workspace MCP** — [#644](https://github.com/taylorwilsdon/google_workspace_mcp/pull/644): default the single-user email to an env var.
- **Future AGI** — [#1327](https://github.com/future-agi/future-agi/pull/1327): scroll fix in the evals log panel.
- **LangChain** — [#15251](https://github.com/langchain-ai/langchain/pull/15251): fixed the `.devcontainer` build.

Proposed and closed without merge, kept here because the work was real: LangChain agent tool-input parser fix ([#14668](https://github.com/langchain-ai/langchain/pull/14668), [#15422](https://github.com/langchain-ai/langchain/pull/15422)); mem0 session-memory scoping, provider env vars, and a hook migration with parallel recall ([#4574](https://github.com/mem0ai/mem0/pull/4574), [#4987](https://github.com/mem0ai/mem0/pull/4987), [#5077](https://github.com/mem0ai/mem0/pull/5077)); OpenClaw gateway startup deferral ([#72932](https://github.com/openclaw/openclaw/pull/72932)); Lossless-Claw SQLite busy-timeout ([#303](https://github.com/Martian-Engineering/lossless-claw/pull/303)). A one-line README listing in OpenAPI Generator ([#17483](https://github.com/OpenAPITools/openapi-generator/pull/17483), 2023) is not counted.

<sub>Full ledger, with maintainer responses per PR: https://www.christopherqueenconsulting.com/work/open-source/?utm_source=github&utm_medium=readme&utm_campaign=open-source</sub>

## 🛠️ Tech I work in

**Languages:** Python · TypeScript · JavaScript · Node.js · Swift · SQL
**AI/LLM:** Claude Agent SDK · OpenAI API · OpenRouter · Ollama · LiteLLM · LangChain · MCP · Agents · Evals · RAG
**Backend & data:** FastAPI · REST · Celery/Redis · MySQL · async / real-time systems · API and systems integration
**Cloud & DevOps:** AWS (Lambda, S3, EC2) · Docker Compose · GitHub Actions · systemd · CI/CD · Git
**Frontend:** React · Streamlit · HTML5 · CSS

## 🚀 Currently

Remote from Jacksonville, FL; travel is fine. Résumé: [christopherqueenconsulting.com/resume](https://www.christopherqueenconsulting.com/resume/?utm_source=github&utm_medium=readme&utm_campaign=resume).

## 🎱 Off the keyboard

Reader, billiards player, and aquarist (yes, I keep the tanks alive too).

## 📫 Connect

- LinkedIn: [linkedin.com/in/christopherqueen](https://www.linkedin.com/in/christopherqueen)
- Email: christopher.queen@gmail.com
- Fixed-scope builds via [Christopher Queen Consulting, LLC](https://christopherqueenconsulting.com)

---
