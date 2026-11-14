"""Offline structural checks for the workflow files and their supporting files.

These tests read the YAML as data. They never touch the network and never run
a workflow. They fail when someone loosens a rule the design depends on: pinned
actions, narrow permissions, one writer per branch, no untrusted text in shell.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
WORKFLOW_FILES = sorted(WORKFLOW_DIR.glob("*.yml"))
NAMES = ["ci", "profile", "snake"]
MAIN_IF = "github.ref == 'refs/heads/main'"

EXPECTED_JOB_PERMISSIONS = {
    "ci": {"ci": {"contents": "read"}, "snake-dry-run": {"contents": "read"}},
    "profile": {
        "generate-text": {"contents": "read"},
        "publish": {"contents": "write"},
        "report": {"issues": "write"},
        "close": {"issues": "write"},
    },
    "snake": {
        "generate-snake": {"contents": "read"},
        "publish": {"contents": "write"},
        "report": {"issues": "write"},
        "close": {"issues": "write"},
    },
}

# Wording that must never appear in public text. Built from fragments so this
# file does not match itself.
FORBIDDEN_TEXT = re.compile(
    "|".join(
        [
            "Click" + "Up",
            r"app\.click" + "up",
            "rol" + "e:",
            "agent-" + "secret",
            "vau" + "lt",
            "1Pass" + "word",
            r"\bQu" + r"in\b",
            "cqc-" + "ea",
        ]
    ),
    re.IGNORECASE,
)

# Home-directory prefixes, also built from fragments.
HOME_PATHS = ("/ho" + "me/", "/Us" + "ers/")

ALLOWED_EXPRESSIONS = [
    r"github\.(token|repository|server_url|run_id|workflow|ref)",
    r"runner\.temp",
    r"inputs\.inject_fault \|\| 'none'",
    r"needs\.[a-z-]+\.result",
    r"needs\.[a-z-]+\.outputs\.[a-z_]+",
    r"steps\.generate\.outputs\.[a-z_]+",
]


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOW_DIR / f"{name}.yml").read_text(encoding="utf-8"))


def text(name: str) -> str:
    return (WORKFLOW_DIR / f"{name}.yml").read_text(encoding="utf-8")


def triggers(wf: dict) -> dict:
    # YAML 1.1 reads the bare key `on` as the boolean True.
    value = wf.get("on", wf.get(True))
    return value if isinstance(value, dict) else {k: None for k in value}


def jobs(name: str) -> dict:
    return load(name)["jobs"]


def steps(job: dict) -> list[dict]:
    return job.get("steps", [])


def all_run_blocks(name: str):
    for job_id, job in jobs(name).items():
        for step in steps(job):
            if "run" in step:
                yield job_id, step["run"]


def uses_lines(name: str) -> list[str]:
    return [
        line
        for line in text(name).splitlines()
        if re.match(r"^\s*-?\s*uses:", line)
    ]


def test_expected_workflow_files_exist():
    assert [p.stem for p in WORKFLOW_FILES] == NAMES


# ------------------------------------------------------------------- pins


@pytest.mark.parametrize("name", NAMES)
def test_every_uses_is_a_full_sha_with_a_version_comment(name):
    lines = uses_lines(name)
    assert lines, "workflow has no uses: lines"
    for line in lines:
        m = re.match(r"^\s*-?\s*uses:\s+(\S+)\s+#\s*(v\d+\.\d+\.\d+)\s*$", line)
        assert m, f"not pinned with a version comment: {line.strip()}"
        action = m.group(1)
        assert not action.startswith("./"), "local actions are not used here"
        assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", action), line.strip()  # preflight: ok


def test_no_third_party_actions():
    for name in NAMES:
        for job_id, job in jobs(name).items():
            for step in steps(job):
                if "uses" in step:
                    assert step["uses"].startswith("actions/"), f"{name}/{job_id}: {step['uses']}"


def test_snake_generator_step():
    for name, job_id in (("snake", "generate-snake"), ("ci", "snake-dry-run")):
        step = next(s for s in steps(jobs(name)[job_id]) if s.get("name") == "Draw the growing snake from the calendar")
        assert step["env"] == {"GITHUB_TOKEN": "${{ github.token }}"}, "the default read-only token is used"
        assert step["run"].strip() == "python scripts/make_growing_snake.py --user gitchrisqueen --out-dir dist"


@pytest.mark.parametrize("name", NAMES)
def test_actions_majors_are_current_enough(name):
    wanted = {
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1": "v7.0.1",
        "actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0": "v7.1.0",
        "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9": "v7.0.2",
        "actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333": "v8.0.2",
    }
    for line in uses_lines(name):
        m = re.match(r"^\s*-?\s*uses:\s+(\S+)\s+#\s*(\S+)", line)
        assert wanted.get(m.group(1)) == m.group(2), f"unexpected pin: {line.strip()}"


# --------------------------------------------------------------- triggers


@pytest.mark.parametrize("name", NAMES)
def test_no_forbidden_triggers(name):
    forbidden = {"pull_request_target", "workflow_run", "issue_comment"}
    assert not forbidden & set(triggers(load(name)))
    code = "\n".join(l for l in text(name).splitlines() if not l.lstrip().startswith("#"))
    for word in forbidden:
        assert word not in code


def test_ci_triggers_have_no_path_filter():
    trig = triggers(load("ci"))
    assert set(trig) == {"pull_request", "push"}
    for value in trig.values():
        assert not value or ("paths" not in value and "paths-ignore" not in value)


def test_ci_push_ignores_only_the_output_branch():
    trig = triggers(load("ci"))
    assert trig["push"] == {"branches-ignore": ["output"]}
    assert not trig["pull_request"]
    code = "\n".join(l for l in text("ci").splitlines() if not l.lstrip().startswith("#"))
    assert "paths" not in code


def test_snake_lint_steps_pass_the_same_max_bytes_as_the_size_loop():
    for name, job_id in (("snake", "generate-snake"), ("snake", "publish"), ("ci", "snake-dry-run")):
        block = "\n".join(s.get("run", "") for s in steps(jobs(name)[job_id]))
        lint_calls = re.findall(r"lint_svg\.py[^\n]*(?:\\\n[^\n]*)*", block)
        assert lint_calls, f"{name}/{job_id} has no lint call"
        for call in lint_calls:
            assert "--max-bytes 1500000" in call, f"{name}/{job_id}"
            assert "--min-bytes 5000" in call
    gen = "\n".join(s.get("run", "") for s in steps(jobs("snake")["generate-snake"]))
    assert '-gt 1500000' in gen


@pytest.mark.parametrize("name,workflow_file", [("profile", "profile.yml"), ("snake", "snake.yml")])
def test_writer_workflow_triggers(name, workflow_file):
    trig = triggers(load(name))
    assert set(trig) == {"schedule", "workflow_dispatch", "push"}
    assert trig["push"]["branches"] == ["main"]
    assert trig["push"]["paths"] == [
        "scripts/**",
        "data/**",
        f".github/workflows/{workflow_file}",
    ]
    crons = [item["cron"] for item in trig["schedule"]]
    assert len(crons) == 1
    minute = int(crons[0].split()[0])
    assert minute % 2 == 1, "schedule at an odd minute, away from the top of the hour"


@pytest.mark.parametrize(
    "name,options", [("profile", ["none", "bad-allowlist", "bad-marker"]), ("snake", ["none", "bad-svg"])]
)
def test_inject_fault_input_is_a_choice(name, options):
    spec = triggers(load(name))["workflow_dispatch"]["inputs"]["inject_fault"]
    assert spec["type"] == "choice"
    assert spec["options"] == options
    assert spec["default"] == "none"


@pytest.mark.parametrize("name", ["profile", "snake"])
def test_inject_fault_reaches_shell_only_through_env(name):
    for line in text(name).splitlines():
        if "inputs.inject_fault" in line and "${{" in line:
            assert line.strip().startswith("INJECT_FAULT:"), line.strip()
    for job_id, job in jobs(name).items():
        for step in steps(job):
            if "inputs.inject_fault" in str(step.get("run", "")):
                pytest.fail(f"{job_id}: inject_fault used directly in run")


# ------------------------------------------------------- shell and contexts


@pytest.mark.parametrize("name", NAMES)
def test_no_expression_inside_run(name):
    for job_id, block in all_run_blocks(name):
        assert "${{" not in block, f"{name}/{job_id}: expression inside run"
        for needle in ("github.event", "github.head_ref", "github.actor"):
            assert needle not in block


@pytest.mark.parametrize("name", NAMES)
def test_every_expression_is_on_the_allow_list(name):
    expressions = re.findall(r"\$\{\{\s*(.*?)\s*\}\}", text(name))
    assert expressions
    for expr in expressions:
        assert any(re.fullmatch(p, expr) for p in ALLOWED_EXPRESSIONS), f"unexpected: {expr}"


@pytest.mark.parametrize("name", NAMES)
def test_no_secrets_context(name):
    assert "secrets." not in text(name)


@pytest.mark.parametrize("name", NAMES)
def test_no_curl_to_shell_and_no_force(name):
    for job_id, block in all_run_blocks(name):
        assert not re.search(r"(curl|wget)[^|\n]*\|\s*(sudo\s+)?(ba|z)?sh(\s|$)", block), job_id
    assert "--force" not in text(name)
    for job_id, block in all_run_blocks(name):
        for line in block.splitlines():
            if re.search(r"\bgit\s+push\b", line):
                assert not re.search(r"(\s-f\b|--force|--mirror|--delete|\s\+\S)", line), line


@pytest.mark.parametrize("name,ref", [("profile", "main"), ("snake", "output")])
def test_pushes_use_one_explicit_refspec(name, ref):
    pushes = [
        line.strip()
        for _, block in all_run_blocks(name)
        for line in block.splitlines()
        if re.search(r"\bgit\s+push\b", line)
    ]
    assert pushes, "the writer workflow must push"
    for line in pushes:
        assert line.endswith(f"origin HEAD:refs/heads/{ref}") or f"origin HEAD:refs/heads/{ref};" in line


# -------------------------------------------------------------- permissions


@pytest.mark.parametrize("name", NAMES)
def test_top_level_permissions_are_empty(name):
    assert load(name)["permissions"] == {}


@pytest.mark.parametrize("name", NAMES)
def test_job_permissions_are_exactly_as_specified(name):
    actual = {job_id: job.get("permissions") for job_id, job in jobs(name).items()}
    assert actual == EXPECTED_JOB_PERMISSIONS[name]


@pytest.mark.parametrize("name", NAMES)
def test_no_job_holds_both_write_scopes(name):
    for job_id, job in jobs(name).items():
        perms = job["permissions"]
        assert not ("contents" in perms and perms["contents"] == "write" and "issues" in perms)


@pytest.mark.parametrize("name", NAMES)
def test_every_job_has_a_timeout(name):
    for job_id, job in jobs(name).items():
        timeout = job.get("timeout-minutes")
        assert isinstance(timeout, int) and 1 <= timeout <= 30, f"{name}/{job_id}"


@pytest.mark.parametrize("name", NAMES)
def test_write_jobs_are_gated_to_main_at_job_level(name):
    wrote = 0
    for job_id, job in jobs(name).items():
        perms = job["permissions"]
        if "write" in perms.values():
            wrote += 1
            assert MAIN_IF in str(job.get("if")), f"{name}/{job_id} needs the main-only job-level if"
    assert wrote == (0 if name == "ci" else 3)


@pytest.mark.parametrize("name", NAMES)
def test_checkout_persists_credentials_only_in_publish_jobs(name):
    for job_id, job in jobs(name).items():
        for step in steps(job):
            if step.get("uses", "").startswith("actions/checkout@"):
                persist = step.get("with", {}).get("persist-credentials")
                if job["permissions"].get("contents") == "write":
                    assert persist is True
                else:
                    assert persist is False, f"{name}/{job_id} checkout must set persist-credentials: false"


# ------------------------------------------------------------- job graphs


def test_profile_job_graph():
    j = jobs("profile")
    assert set(j) == {"generate-text", "publish", "report", "close"}
    assert j["publish"]["needs"] == "generate-text"
    assert "always()" in j["publish"]["if"]
    assert "has_good_block == 'true'" in j["publish"]["if"]
    assert j["publish"]["concurrency"] == {"group": "profile-main", "cancel-in-progress": False}
    assert set(j["generate-text"]["outputs"]) == {"has_good_block", "failed_blocks"}
    upload = [s for s in steps(j["generate-text"]) if s.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(upload) == 1 and upload[0]["if"] == "always()"
    assert j["report"]["if"].startswith("failure()")
    assert j["close"]["if"].startswith("needs.generate-text.result == 'success'")


def test_snake_job_graph():
    j = jobs("snake")
    assert set(j) == {"generate-snake", "publish", "report", "close"}
    assert j["publish"]["needs"] == "generate-snake"
    assert "needs.generate-snake.result == 'success'" in j["publish"]["if"]
    assert j["publish"]["concurrency"] == {"group": "output-branch", "cancel-in-progress": False}
    assert j["report"]["if"].startswith("failure()")


@pytest.mark.parametrize("name", ["profile", "snake"])
def test_report_and_close_touch_only_their_own_label(name):
    other = "snake" if name == "profile" else "profile"
    raw = text(name)
    assert f"profile-automation:{name}" in raw
    assert f"profile-automation:{other}" not in raw
    for job_id in ("report", "close"):
        env = jobs(name)[job_id]["env"]
        assert env["LABEL"] == f"profile-automation:{name}"
        for step in steps(jobs(name)[job_id]):
            assert "uses" not in step, "report and close run only first-party shell"
        block = "\n".join(s["run"] for s in steps(jobs(name)[job_id]))
        assert '--label "${LABEL}"' in block
        assert "gh issue list" in block
        assert "issues are disabled".lower() in block.lower()


def test_profile_publish_guards_before_it_commits():
    block = "\n".join(s.get("run", "") for s in steps(jobs("profile")["publish"]))
    assert block.index("guard_publish.py") < block.index("git commit")
    assert "--git-diff" in block and "--allowlist data/allowlist.json" in block
    assert 'cp -- "${ARTIFACT_DIR}/README.md" README.md' in block
    assert "cp -r" not in block and "cp -R" not in block
    assert 'git commit --message "chore: refresh profile data"' in block
    assert "git add -- README.md" in block
    assert "github-actions[bot]" in block
    # Nothing is executed from the artifact.
    assert "ARTIFACT_DIR}/scripts" not in block and "python ${ARTIFACT_DIR}" not in block


def test_profile_publish_fails_the_run_when_generation_failed():
    last = steps(jobs("profile")["publish"])[-1]
    assert last["if"] == "always()"
    assert "exit 1" in last["run"]


def test_profile_generate_text_is_first_party_only_and_runs_the_generator_once():
    job = jobs("profile")["generate-text"]
    assert all(s.get("uses", "").startswith("actions/") for s in steps(job) if "uses" in s)
    runs = [s["run"] for s in steps(job) if "update_profile.py" in s.get("run", "")]
    assert len(runs) == 1
    assert '--inject-fault "${INJECT_FAULT}"' in runs[0]
    assert "none | bad-allowlist | bad-marker" in runs[0]


def test_snake_publish_bootstrap_and_no_force_flags():
    block = "\n".join(s.get("run", "") for s in steps(jobs("snake")["publish"]))
    assert "git ls-remote --exit-code --heads origin output" in block
    assert "git checkout --orphan output" in block
    assert "git rm -rf --quiet ." in block
    assert "git push origin HEAD:refs/heads/output" in block
    assert "--force" not in block and "--force-with-lease" not in block
    assert block.index("lint_svg.py") < block.index("git push")
    assert "files=(snake.svg snake-dark.svg snake-static-light.svg snake-static-dark.svg)" in block
    assert 'git commit --message "chore: refresh snake assets"' in block


def test_snake_generate_runs_lint_and_size_check_before_upload():
    job_steps = steps(jobs("snake")["generate-snake"])
    names = [s["name"] for s in job_steps]
    assert names.index("Draw the growing snake from the calendar") < names.index(
        "Lint and size-check the SVGs"
    ) < names.index("Upload the validated SVGs")
    lint = next(s["run"] for s in job_steps if s["name"].startswith("Lint and size-check"))
    assert "--profile chart" in lint and "--require-opaque-background" in lint
    upload = next(s for s in job_steps if s["name"] == "Upload the validated SVGs")
    assert "if" not in upload, "only validated files are uploaded"


def test_ci_steps():
    job = jobs("ci")["ci"]
    block = "\n".join(s.get("run", "") for s in steps(job))
    for needle in (
        "python -m pytest tests -q",
        "actionlint",
        "scripts/build_assets.py --check",
        "scripts/check_contrast.py assets/colors.json",
        "scripts/update_profile.py --readme README.md",
        "scripts/guard_publish.py",
        "--require-hashes",
        "sha256sum --check --strict",
    ):
        assert needle in block, needle
    sha = job["env"]["ACTIONLINT_SHA256"]
    assert re.fullmatch(r"[0-9a-f]{64}", sha)
    assert re.fullmatch(r"\d+\.\d+\.\d+", job["env"]["ACTIONLINT_VERSION"])  # preflight: ok
    upload = [s for s in steps(job) if s.get("uses", "").startswith("actions/upload-artifact@")]
    assert upload and upload[0]["if"] == "always()"
    # The generator reads with the read-only token.
    gen = next(s for s in steps(job) if "update_profile.py" in s.get("run", ""))
    assert gen["env"]["GITHUB_TOKEN"] == "${{ github.token }}"
    snake_steps = steps(jobs("ci")["snake-dry-run"])
    assert any(s.get("with", {}).get("name") == "snake-artifacts" for s in snake_steps)


# ---------------------------------------------------- supporting files


def test_requirements_are_hash_pinned():
    lines = (ROOT / "requirements-ci.txt").read_text(encoding="utf-8").splitlines()
    entries = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        entries.append(s)
    joined = "\n".join(entries).replace("\\\n", " ")
    requirements = [e for e in re.split(r"\n(?=[A-Za-z])", joined) if e]
    assert requirements
    for req in requirements:
        assert re.match(r"^[A-Za-z0-9_.-]+==\d", req), req
        assert "--hash=sha256:" in req, req
    assert not re.search(r"(git\+|https?://|^-e )", joined, re.M)


def test_dependabot_covers_actions_and_pip_without_auto_merge():
    cfg = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    assert cfg["version"] == 2
    ecosystems = {u["package-ecosystem"]: u for u in cfg["updates"]}
    assert set(ecosystems) == {"github-actions", "pip"}
    for u in ecosystems.values():
        assert u["directory"] == "/"
    raw = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8").lower()
    assert "automerge" not in raw and "auto-merge: true" not in raw


def test_codeowners_names_the_owner():
    lines = [
        l.split()
        for l in (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.startswith("#")
    ]
    assert ["*", "@gitchrisqueen"] in lines
    assert all(l[1:] == ["@gitchrisqueen"] for l in lines)


def test_no_internal_wording_anywhere_in_the_tree():
    skip_dirs = {".git", "__pycache__", ".pytest_cache", "node_modules"}
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in skip_dirs for part in path.relative_to(ROOT).parts):
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(body.splitlines(), 1):
            if FORBIDDEN_TEXT.search(line) or any(h in line for h in HOME_PATHS):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}")
    assert not hits, hits


# ------------------------------------------------------ maintenance doc


def maintenance() -> str:
    return (ROOT / "docs" / "MAINTENANCE.md").read_text(encoding="utf-8")


def test_maintenance_doc_has_the_required_content():
    doc = maintenance()
    for needle in (
        'gh label create "profile-automation:profile"',
        'gh label create "profile-automation:snake"',
        "gh api repos/gitchrisqueen/gitchrisqueen/actions/permissions",
        "gh repo view gitchrisqueen/gitchrisqueen --json hasIssuesEnabled",
        "gh run download",
        "git push origin HEAD:refs/heads/output",
        "curl -sI",
        "gh workflow run profile.yml --ref main -f inject_fault=bad-allowlist",
        "gh workflow run profile.yml --ref main -f inject_fault=none",
        "gh workflow run snake.yml --ref main -f inject_fault=bad-svg",
        "PURGE",
        "gh workflow enable profile.yml",
        "gh workflow enable snake.yml",
        "gh workflow disable profile.yml",
        "gh workflow disable snake.yml",
        "startup_failure",
        "cancelled",
        "timed out",
        "assets/colors.json",
        "python scripts/check_contrast.py assets/colors.json",
        "profile-v1-pre",
        "overwritten",
        "a ruleset requiring status checks or PRs on main breaks the publish job",
        "never merge on their own",
        "git revert",
    ):
        assert needle in doc, f"MAINTENANCE.md is missing: {needle}"
    assert "--force" not in doc


def test_maintenance_labels_match_the_workflows():
    doc = maintenance()
    created = set(re.findall(r'gh label create "(profile-automation:[a-z]+)"', doc))
    used = {
        load(name)["jobs"]["report"]["env"]["LABEL"] for name in ("profile", "snake")
    }
    assert created == used


@pytest.mark.parametrize("name", NAMES)
def test_scheduled_workflows_never_pass_allow_shrink(name):
    assert "allow-shrink" not in text(name)


# ------------------------------------------------- maintenance doc: operations


def data_files_doc() -> str:
    return (ROOT / "docs" / "DATA-FILES.md").read_text(encoding="utf-8")


def fenced_blocks(doc: str) -> list[str]:
    return re.findall(r"^```[a-z]*\n(.*?)^```", doc, flags=re.S | re.M)


def section(doc: str, start: str, end: str) -> str:
    a = doc.index(start)
    return doc[a : doc.index(end, a)]


PATH_RE = re.compile(
    r"(?<![\w/.:-])((?:\.github|scripts|data|docs|assets|tests)/[\w./*-]*[\w*]|README\.md|requirements-ci\.txt)"
)


@pytest.mark.parametrize("doc_name", ["MAINTENANCE.md", "DATA-FILES.md"])
def test_every_repo_path_named_in_the_docs_resolves(doc_name):
    doc = (ROOT / "docs" / doc_name).read_text(encoding="utf-8")
    found = set(PATH_RE.findall(doc))
    assert found, "the path pattern found nothing"
    for token in sorted(found):
        if any(ch in token for ch in "*"):
            assert list(ROOT.glob(token)), f"{doc_name}: glob matches nothing: {token}"
        else:
            assert (ROOT / token).exists(), f"{doc_name}: path does not exist: {token}"


def test_maintenance_points_to_the_data_files_doc():
    doc = maintenance()
    assert "docs/DATA-FILES.md" in doc
    assert "data/README-notes.md" not in doc
    assert (ROOT / "docs" / "DATA-FILES.md").is_file()


def test_data_files_doc_covers_every_file_and_field():
    doc = data_files_doc()
    for needle in (
        "data/allowlist.json", "data/pr-notes.json", "data/flagships.json",
        "github_user", "exclude_org", "merged_upstream", "flagships", "excluded_prs",
        "owner/repo#N", "140 characters", "name", "repo", "workflow", "check",
        "issue 14631", "Daily pipeline run", "does not mean the data is healthy",
    ):
        assert needle in doc, f"DATA-FILES.md is missing: {needle}"
    assert "Daily pipeline run" in maintenance()
    assert "not that the data is healthy" in maintenance() or "does not mean the data is healthy" in maintenance()


def test_every_gh_command_in_the_runbook_names_the_repository():
    for number, line in enumerate(maintenance().splitlines(), 1):
        for match in re.finditer(r"\bgh (?!auth )[^`\n]*", line):
            assert "gitchrisqueen/gitchrisqueen" in match.group(0), f"line {number}: {match.group(0)[:80]}"


def test_where_to_run_paragraph_comes_first_and_covers_the_basics():
    doc = maintenance()
    assert doc.index("## Where to run these commands") < doc.index("## How it works")
    block = section(doc, "## Where to run these commands", "## How it works")
    for needle in ("--repo gitchrisqueen/gitchrisqueen", "git -C <clone>", "gh auth setup-git", "cd ..", "scratch clone"):
        assert needle in block, needle
    seed = doc[doc.index("3. Seed the `output` branch") :]
    assert seed.index("`cd ..`") < seed.index("```")  # the note comes before the code block
    assert "gh auth setup-git" in fenced_blocks(seed)[0]
    assert fenced_blocks(seed)[0].rstrip().endswith("cd ..")


def test_drills_wait_for_the_run_and_assert_only_afterwards():
    drills = section(maintenance(), "### After the pull request is merged", "### If the first run")
    blocks = [b for b in fenced_blocks(drills) if "gh workflow run" in b]
    assert len(blocks) == 5
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            if "gh workflow run" in line:
                nxt = lines[i + 1]
                assert "sleep 15" in nxt and "gh run list" in nxt and "databaseId" in nxt, nxt
                assert 'gh run watch "${id}"' in nxt and "--exit-status || true" in nxt
                assert "--event workflow_dispatch" in nxt
        last_watch = max(i for i, l in enumerate(lines) if "gh run watch" in l)
        first_dispatch = min(i for i, l in enumerate(lines) if "gh workflow run" in l)
        for i, line in enumerate(lines):
            if "gh issue list" in line or line.startswith("after=") or 'test "${before}"' in line:
                assert i > last_watch, f"assertion before the watch: {line[:60]}"
            if line.startswith("before="):
                assert i < first_dispatch, "the 'before' value must be taken before dispatch"
    assert "`event` must be `workflow_dispatch`" in drills and "`createdAt`" in drills


def test_snake_drill_compares_before_and_after_with_ls_remote():
    drills = section(maintenance(), "7. Fault-injection drill for the snake workflow", "8. Rehearse")
    block = fenced_blocks(drills)[0]
    assert block.count("git ls-remote") == 2
    assert block.index("before=") < block.index("gh workflow run") < block.index("gh run watch") < block.index("after=")


def test_monitoring_is_described_as_a_manual_weekly_task():
    doc = maintenance()
    mon = section(doc, "## Monitoring and the 60-day rule", "## Detection table")
    assert "manual task owned by the repository owner" in mon
    assert "Nothing in this repository watches the workflows" in mon
    for needle in (
        "--workflow profile.yml --status success", "--workflow snake.yml --status success",
        "actions/workflows --jq", "commits/output --jq .commit.committer.date", "date -u",
    ):
        assert needle in mon, needle
    assert "scheduled check" not in doc
    assert "runs every 7 days" not in doc
    detection = section(doc, "## Detection table", "## Rollback")
    assert "the scheduled check is the alert" not in detection
    assert "weekly manual check" in detection


def test_prerequisites_include_watching_issues_with_a_check_command():
    pre = section(maintenance(), "## Prerequisites, with a check for each", "Create the labels")
    row = next(l for l in pre.splitlines() if l.startswith("| You are watching Issues"))
    assert "gh api repos/gitchrisqueen/gitchrisqueen/subscription" in row
    assert "subscribed" in row and "ignored" in row


def test_ci_notes_cover_the_live_api_and_cost():
    doc = maintenance()
    assert "reads the live GitHub API" in doc and "re-run fixes it" in doc
    assert "public" in doc and "standard GitHub-hosted runner" in doc
    assert "except a push to the `output` branch" in doc


def test_rollback_step_one_cancels_in_progress_runs():
    step = section(maintenance(), "1. Stop the writers", "2. Restore the README")
    assert "gh workflow disable profile.yml" in step and "gh workflow disable snake.yml" in step
    assert "gh run cancel <run-id> --repo gitchrisqueen/gitchrisqueen" in step
    assert step.index("gh workflow disable") < step.index("gh run cancel")


def test_remove_a_merged_row_procedure_is_documented():
    doc = maintenance()
    block = section(doc, "## Remove a row from the merged block", "\x00") if False else doc[doc.index("## Remove a row from the merged block") :]
    for needle in (
        "shrunken result", "fewer rows than the base", "--allow-shrink", "data/allowlist.json", "README.md",
        "update_profile.py --readme README.md --allow-shrink", "guard_publish.py", "guard: ok", "excluded_prs",
    ):
        assert needle in block, needle
    assert "never pass the flag" in block


def test_panthera_check_text_is_pinned_in_the_data_file():
    import json

    flags = json.loads((ROOT / "data" / "flagships.json").read_text(encoding="utf-8"))["flagships"]
    check = next(e["check"] for e in flags if e["repo"].endswith("/panthera"))
    assert check == "Daily pipeline run"


@pytest.mark.parametrize("name", ["profile", "snake"])
def test_gh_repo_view_names_the_repository_because_the_issue_jobs_have_no_checkout(name):
    code = "\n".join(l for l in text(name).splitlines() if not l.lstrip().startswith("#"))
    calls = re.findall(r"gh repo view[^\n]*", code)
    assert calls, name
    assert all('"${GH_REPO}"' in c for c in calls), calls
