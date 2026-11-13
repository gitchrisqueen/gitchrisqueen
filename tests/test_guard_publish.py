"""Offline tests for scripts/guard_publish.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import guard_publish as gp  # noqa: E402

ALLOWLIST = ROOT / "data" / "allowlist.json"
SM, EM = gp.marker_start("MERGED-UPSTREAM"), gp.marker_end("MERGED-UPSTREAM")
SF, EF = gp.marker_start("FLAGSHIPS"), gp.marker_end("FLAGSHIPS")

ROW_A = ("- [langchain-ai/langchain #15251](https://github.com/langchain-ai/langchain/pull/15251): "
         "Fixed the dev container build")
ROW_B = ("- [future-agi/future-agi #1327](https://github.com/future-agi/future-agi/pull/1327): "
         "`fix(evals): add scroll (#1071)`")
ROW_C = "- [PostHog/posthog-openclaw #15](https://github.com/PostHog/posthog-openclaw/pull/15): PR #15"
FLAG_1 = "| [panthera](https://github.com/gitchrisqueen/panthera) | Daily scheduled pipeline run | passing |"
FLAG_2 = "| [hearing-copilot](https://github.com/gitchrisqueen/hearing-copilot) | Automated tests and lint | failing |"


def readme(merged=(ROW_A,), flags=(gp.FLAG_HEADER, gp.FLAG_SEPARATOR, FLAG_1),
           before="Intro line.", after="Outro line."):
    parts = [before, "", SF, *flags, EF, "", "Middle text.", "", SM, *merged, EM, "", after, ""]
    return "\n".join(parts)


@pytest.fixture
def paths(tmp_path):
    def make(base_text, new_text):
        base = tmp_path / "README.base.md"
        new = tmp_path / "README.md"
        base.write_text(base_text, encoding="utf-8")
        new.write_text(new_text, encoding="utf-8")
        return str(base), str(new)
    return make


def run(paths, base_text, new_text, **kw):
    base, new = paths(base_text, new_text)
    return gp.check(base, new, str(ALLOWLIST), **kw)


def has(problems, needle):
    return any(needle in p for p in problems)


# ---------------------------------------------------------------- passing cases
def test_passes_when_only_block_lines_change(paths):
    base = readme(merged=(ROW_A,))
    new = readme(merged=(ROW_B, ROW_A, ROW_C), flags=(gp.FLAG_HEADER, gp.FLAG_SEPARATOR, FLAG_1, FLAG_2))
    assert run(paths, base, new) == []


def test_passes_with_empty_base_blocks(paths):
    base = readme(merged=(), flags=())
    assert run(paths, base, readme()) == []


def test_identical_files_pass(paths):
    assert run(paths, readme(), readme()) == []


def test_cli_exit_codes(paths, capsys):
    base, new = paths(readme(), readme(merged=(ROW_B, ROW_A)))
    assert gp.main(["--base", base, "--new", new, "--allowlist", str(ALLOWLIST)]) == 0
    assert "guard: ok" in capsys.readouterr().out
    base, new = paths(readme(), readme(after="Changed outro."))
    assert gp.main(["--base", base, "--new", new, "--allowlist", str(ALLOWLIST)]) == 1
    assert "FAILED" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exc:
        gp.main(["--base", base])
    assert exc.value.code == 2


# ---------------------------------------------------------------- only marker lines differ
@pytest.mark.parametrize("field", ["before", "after"])
def test_text_outside_markers_must_not_change(paths, field):
    problems = run(paths, readme(), readme(**{field: "Changed."}))
    assert has(problems, "outside the generated blocks")


def test_text_between_the_two_blocks_must_not_change(paths):
    base = readme()
    assert has(run(paths, base, base.replace("Middle text.", "Middle text, edited.")), "outside")


def test_extra_line_outside_blocks_fails(paths):
    base = readme()
    assert has(run(paths, base, base + "extra line\n"), "outside")


def test_marker_line_edit_fails(paths):
    base = readme()
    new = base.replace(SM, "<!-- MERGED-UPSTREAM:START  -->")
    problems = run(paths, base, new)
    assert has(problems, "MERGED-UPSTREAM needs exactly one")


def test_blocks_swapped_fails(paths):
    base = readme()
    new = "\n".join(["Intro line.", "", SM, ROW_A, EM, "", "Middle text.", "", SF, gp.FLAG_HEADER, gp.FLAG_SEPARATOR,
                      FLAG_1, EF, "", "Outro line.", ""])
    assert has(run(paths, base, new), "outside")


# ---------------------------------------------------------------- marker structure
@pytest.mark.parametrize("label,mutate", [
    ("missing-start", lambda t: t.replace(SM + "\n", "")),
    ("missing-end", lambda t: t.replace(EM + "\n", "")),
    ("duplicate-start", lambda t: t.replace(SM, SM + "\n" + SM)),
    ("duplicate-end", lambda t: t.replace(EM, EM + "\n" + EM)),
    ("end-before-start", lambda t: t.replace(SM + "\n" + ROW_A + "\n" + EM, EM + "\n" + ROW_A + "\n" + SM)),
    ("inline", lambda t: t.replace(SM, "text " + SM)),
    ("trailing-text", lambda t: t.replace(EF, EF + " trailing")),
    ("overlap", lambda t: t.replace(SM, SM + "\n" + SF + "\n" + EF)),
])
def test_marker_problems_in_new_fail(paths, label, mutate):
    base = readme()
    problems = run(paths, base, mutate(base))
    assert problems, label


def test_marker_problems_in_base_fail(paths):
    base = readme().replace(EM + "\n", "")
    assert has(run(paths, base, readme()), "base:")


def test_nested_blocks_fail(paths):
    text = "\n".join([SM, SF, EF, EM, ""])
    assert has(run(paths, text, text), "overlap")


# ---------------------------------------------------------------- row grammar
@pytest.mark.parametrize("bad_line", [
    "<b>raw html</b>",
    "<img src=x onerror=alert(1)>",
    "![pixel](https://github.com/a/b.png)",
    "- [a/b #1](https://github.com/a/b/pull/1): <script>alert(1)</script>",
    "- [a/b #1](https://github.com/a/b/pull/1): note [link](https://github.com/x/y)",
    "- [a/b #1](https://github.com/a/b/pull/1): see https://github.com/x/y",
    "- [a/b #1](https://github.com/a/b/pull/1): see www.example.com",
    "- [a/b #1](https://evil.example/a/b/pull/1): note",
    "- [a/b #1](https://github.com.evil.example/a/b/pull/1): note",
    "- [a/b #1](http://github.com/a/b/pull/1): note",
    "- [a/b #1](https://github.com/a/b/pull/2): mismatched number",
    "- [a/b #1](https://github.com/c/d/pull/1): mismatched repo",
    "- [a/b #1](https://github.com/a/b/pull/1): ",
    "- [a/b #1](https://github.com/a/b/pull/1): note with @mention",
    "- [a/b #1](https://github.com/a/b/pull/1): note | pipe",
    "- [a/b #1](https://github.com/a/b/pull/1): note with `tick` inside",
    "- [a/b #1](https://github.com/a/b/pull/1): `code with <angle>`",
    "- [a/b #1](https://github.com/a/b/pull/1): `` double fence ``",
    "- [a/b #1](https://github.com/a/b/pull/1): trailing space ",
    "* [a/b #1](https://github.com/a/b/pull/1): wrong bullet",
    "- [a/b #1](https://github.com/a/b/pull/1): merged by someone",   # fine text, but see allowlist below
    "",
    "plain prose line",
    "<!-- comment -->",
])
def test_merged_block_rejects_non_grammar_lines(paths, bad_line):
    base = readme()
    new = readme(merged=(ROW_A, bad_line))
    problems = run(paths, base, new)
    assert problems, bad_line


def test_merged_row_with_unlisted_repo_fails(paths):
    row = "- [evil-org/evil-repo #1](https://github.com/evil-org/evil-repo/pull/1): PR #1"
    problems = run(paths, readme(), readme(merged=(ROW_A, row)))
    assert has(problems, "not in the allowlist")


def test_repo_check_is_case_insensitive_but_exact_otherwise(paths):
    row = "- [LangChain-AI/LangChain #15251](https://github.com/LangChain-AI/LangChain/pull/15251): PR #15251"
    assert run(paths, readme(), readme(merged=(row,))) == []
    row = "- [langchain-ai/langchain2 #1](https://github.com/langchain-ai/langchain2/pull/1): PR #1"
    assert has(run(paths, readme(), readme(merged=(row,))), "not in the allowlist")


def test_flagship_repo_in_merged_block_fails(paths):
    row = "- [gitchrisqueen/panthera #1](https://github.com/gitchrisqueen/panthera/pull/1): PR #1"
    assert has(run(paths, readme(), readme(merged=(row,))), "not in the allowlist")


def test_merged_repo_in_flagship_block_fails(paths):
    row = "| [LangChain](https://github.com/langchain-ai/langchain) | Automated tests | passing |"
    new = readme(flags=(gp.FLAG_HEADER, gp.FLAG_SEPARATOR, row))
    assert has(run(paths, readme(), new), "not in the allowlist")


@pytest.mark.parametrize("bad_row", [
    "| [A | B](https://github.com/gitchrisqueen/panthera) | check | passing |",       # pipe in name
    "| [A](https://github.com/gitchrisqueen/panthera) | check | great |",             # status not a word
    "| [A](https://github.com/gitchrisqueen/panthera) | check | passing | extra |",   # extra column
    "| [A](https://github.com/gitchrisqueen/panthera) | passing |",                   # missing column
    "| [A](https://evil.example/gitchrisqueen/panthera) | check | passing |",
    "| ![A](https://github.com/gitchrisqueen/panthera.png) | check | passing |",
    "| [A](https://github.com/gitchrisqueen/panthera) | <b>check</b> | passing |",
    "| [A](https://github.com/gitchrisqueen/panthera) | check www.x.io | passing |",
    "| A | check | passing |",
    "",
])
def test_flagship_block_rejects_bad_rows(paths, bad_row):
    new = readme(flags=(gp.FLAG_HEADER, gp.FLAG_SEPARATOR, FLAG_1, bad_row))
    assert run(paths, readme(), new), bad_row


@pytest.mark.parametrize("flags", [
    (FLAG_1,),                                                            # no header or separator
    ("| Repo | Check | State |", gp.FLAG_SEPARATOR, FLAG_1),
    (gp.FLAG_HEADER, "|---|---|---|", FLAG_1),
    (gp.FLAG_HEADER,),
])
def test_flagship_header_and_separator_are_exact(paths, flags):
    assert run(paths, readme(), readme(flags=flags))


def test_block_may_not_become_empty(paths):
    assert has(run(paths, readme(), readme(merged=())), "became empty")
    assert has(run(paths, readme(), readme(flags=())), "became empty")


def test_merged_block_may_not_shrink(paths):
    base = readme(merged=(ROW_A, ROW_B))
    assert has(run(paths, base, readme(merged=(ROW_A,))), "fewer rows")


def test_problem_messages_do_not_echo_content(paths):
    hostile = "- [a/b #1](https://github.com/a/b/pull/1): <script>HOSTILE-MARKER</script>"
    problems = run(paths, readme(), readme(merged=(ROW_A, hostile)))
    assert problems and not any("HOSTILE-MARKER" in p or "script" in p for p in problems)
    assert has(problems, "line ")


# ---------------------------------------------------------------- allowlist file
def test_malformed_allowlist_fails(paths, tmp_path):
    base, new = paths(readme(), readme())
    bad = tmp_path / "allow.json"
    for content in ("not json", "{}", json.dumps({"merged_upstream": [], "flagships": ["a/b"]}),
                    json.dumps({"merged_upstream": ["a/b"], "flagships": ["bad repo"]})):
        bad.write_text(content)
        assert has(gp.check(base, new, str(bad)), "allowlist")


# ---------------------------------------------------------------- symlinks and files
def test_symlinked_new_file_fails(paths, tmp_path):
    base, new = paths(readme(), readme())
    real = tmp_path / "real.md"
    real.write_text(readme())
    Path(new).unlink()
    Path(new).symlink_to(real)
    assert has(gp.check(base, new, str(ALLOWLIST)), "symlink")


def test_symlinked_base_and_allowlist_fail(paths, tmp_path):
    base, new = paths(readme(), readme())
    link = tmp_path / "base-link.md"
    link.symlink_to(base)
    assert has(gp.check(str(link), new, str(ALLOWLIST)), "base: is a symlink")
    alink = tmp_path / "allow-link.json"
    alink.symlink_to(ALLOWLIST)
    assert has(gp.check(base, new, str(alink)), "allowlist: is a symlink")


def test_missing_files_fail(tmp_path):
    problems = gp.check(str(tmp_path / "nope1"), str(tmp_path / "nope2"), str(tmp_path / "nope3"))
    assert len(problems) == 3


def test_symlink_anywhere_in_tree_fails_with_root(paths, tmp_path):
    base, new = paths(readme(), readme())
    tree = tmp_path / "tree"
    (tree / "assets").mkdir(parents=True)
    (tree / "assets" / "a.svg").write_text("<svg/>")
    assert gp.check(base, new, str(ALLOWLIST), root=str(tree)) == []
    (tree / "assets" / "evil.svg").symlink_to(tree / "assets" / "a.svg")
    assert has(gp.check(base, new, str(ALLOWLIST), root=str(tree)), "symlink present")
    (tree / "assets" / "evil.svg").unlink()
    (tree / "linkdir").symlink_to(tree / "assets", target_is_directory=True)
    assert has(gp.check(base, new, str(ALLOWLIST), root=str(tree)), "symlink present")


def test_non_utf8_input_fails(tmp_path):
    base, new = tmp_path / "b.md", tmp_path / "n.md"
    base.write_bytes(b"\xff\xfe")
    new.write_text(readme())
    assert has(gp.check(str(base), str(new), str(ALLOWLIST)), "base:")


# ---------------------------------------------------------------- git diff
def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    (r / "README.md").write_text(readme())
    (r / "other.txt").write_text("one\n")
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "init")
    return r


def test_git_diff_allows_only_readme(repo, tmp_path):
    base = tmp_path / "README.base.md"
    base.write_text(readme())
    (repo / "README.md").write_text(readme(merged=(ROW_B, ROW_A)))
    args = (str(base), str(repo / "README.md"), str(ALLOWLIST))
    assert gp.check(*args, root=str(repo), git_diff=True) == []
    (repo / "other.txt").write_text("two\n")
    assert has(gp.check(*args, root=str(repo), git_diff=True), "other than README.md")


def test_git_diff_sees_staged_changes(repo, tmp_path):
    base = tmp_path / "README.base.md"
    base.write_text(readme())
    (repo / "other.txt").write_text("staged\n")
    git(repo, "add", "other.txt")
    problems = gp.check(str(base), str(repo / "README.md"), str(ALLOWLIST), root=str(repo), git_diff=True)
    assert has(problems, "other than README.md")


def test_git_diff_failure_is_a_problem(tmp_path):
    base = tmp_path / "b.md"
    base.write_text(readme())
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    (not_a_repo / "README.md").write_text(readme())
    problems = gp.check(str(base), str(not_a_repo / "README.md"), str(ALLOWLIST),
                        root=str(not_a_repo), git_diff=True)
    assert has(problems, "could not run git diff")


def test_git_invocations_are_read_only_and_never_forced(monkeypatch, tmp_path):
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout=b"README.md\0", stderr=b"")

    monkeypatch.setattr(gp.subprocess, "run", fake_run)
    assert gp.git_changed_files(str(tmp_path)) == ["README.md"]
    assert seen
    for cmd in seen:
        assert cmd[0] == "git" and "diff" in cmd and "--name-only" in cmd
        assert not {"--force", "-f", "--force-with-lease", "push", "reset", "checkout", "clean"} & set(cmd)
    src = (ROOT / "scripts" / "guard_publish.py").read_text()
    for needle in ("--force", "git push", "os.system"):
        assert needle not in src


def test_git_diff_flag_without_root_scans_current_directory(monkeypatch, paths, tmp_path):
    base, new = paths(readme(), readme())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gp, "git_changed_files", lambda root: ["README.md"])
    assert gp.check(base, new, str(ALLOWLIST), git_diff=True) == []
    monkeypatch.setattr(gp, "git_changed_files", lambda root: ["README.md", ".github/workflows/x.yml"])
    assert has(gp.check(base, new, str(ALLOWLIST), git_diff=True), "other than README.md")
