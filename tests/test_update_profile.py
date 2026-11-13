"""Offline tests for scripts/update_profile.py (network is blocked; urlopen is faked)."""
from __future__ import annotations

import argparse
import copy
import io
import json
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import Message
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import guard_publish as gp  # noqa: E402
import update_profile as up  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "api"
DATA = ROOT / "data"
TOKEN = "ghs_" + "t" * 24
BODY_SENTINEL = "SECRET-BODY-SENTINEL"
HEADER_SENTINEL = "SECRET-HEADER-SENTINEL"

START_M, END_M = up.marker_start("MERGED-UPSTREAM"), up.marker_end("MERGED-UPSTREAM")
START_F, END_F = up.marker_start("FLAGSHIPS"), up.marker_end("FLAGSHIPS")

README_TMPL = f"""# Example Name

Hand-written intro that must never change.

## Status

{START_F}
{END_F}

## Merged

Hand-written merged intro.

{START_M}
{END_M}

Closed without merge: hand-written sentence.
"""


def load(name):
    return json.loads((FIX / name).read_text())


SEARCH = load("search_merged.json")
REPO_TEMPLATE = load("repo_public.json")
DEFAULT_BRANCH = {"christopherqueenconsulting/cpcc_task_automation": "master"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*a, **k):
        raise AssertionError("network access attempted outside a fake")

    monkeypatch.setattr(urllib.request, "urlopen", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)


# ---------------------------------------------------------------- fake API
class Err:
    def __init__(self, code, headers=None):
        self.code = code
        self.headers = headers or {}


class Seq:
    """Sequential responses; the last one repeats."""

    def __init__(self, *items):
        self.items = list(items)

    def next(self):
        return self.items.pop(0) if len(self.items) > 1 else self.items[0]


class FakeResp:
    def __init__(self, body: bytes, url: str, status: int = 200):
        self._body, self._url, self._status = body, url, status

    def read(self, n=-1):
        return self._body if n < 0 else self._body[:n]

    def getcode(self):
        return self._status

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeGitHub:
    def __init__(self):
        self.routes = []
        self.calls = []
        self.sleeps = []
        self.auth_headers = []

    def route(self, pattern, handler):
        self.routes.append((re.compile(pattern), handler))

    def override(self, pattern, handler):
        self.routes.insert(0, (re.compile(pattern), handler))

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    def count(self, pattern):
        rx = re.compile(pattern)
        return sum(1 for path, _ in self.calls if rx.fullmatch(path))

    def __call__(self, req, timeout=None):
        url = req.full_url
        assert url.startswith("https://api.github.com/"), url
        assert req.get_method() == "GET"
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        self.calls.append((parsed.path, query))
        self.auth_headers.append(req.get_header("Authorization"))
        for rx, handler in self.routes:
            if rx.fullmatch(parsed.path):
                resp = handler.next() if isinstance(handler, Seq) else handler
                if callable(resp):
                    resp = resp(parsed.path, query)
                if isinstance(resp, Err):
                    hdrs = Message()
                    for k, v in resp.headers.items():
                        hdrs[k] = v
                    hdrs["X-Sentinel"] = HEADER_SENTINEL
                    raise urllib.error.HTTPError(url, resp.code, "err", hdrs,
                                                 io.BytesIO(BODY_SENTINEL.encode()))
                if isinstance(resp, BaseException):
                    raise resp
                return FakeResp(json.dumps(resp).encode(), url)
        raise AssertionError(f"unrouted request {parsed.path}")


def paged_search(items, total=None):
    def handler(path, q):
        page, per = int(q["page"][0]), int(q["per_page"][0])
        return {"total_count": len(items) if total is None else total,
                "incomplete_results": False,
                "items": items[(page - 1) * per: page * per]}
    return handler


def repo_handler(path, q):
    m = re.fullmatch(r"/repos/([^/]+)/([^/]+)", path)
    data = copy.deepcopy(REPO_TEMPLATE)
    data["full_name"] = f"{m.group(1)}/{m.group(2)}"
    data["default_branch"] = DEFAULT_BRANCH.get(data["full_name"].lower(), "main")
    return data


def default_fake(items=None):
    fake = FakeGitHub()
    fake.route(r"/search/issues", paged_search(copy.deepcopy(SEARCH["items"] if items is None else items)))
    fake.route(r"/repos/[^/]+/[^/]+", repo_handler)
    fake.route(r"/repos/[^/]+/[^/]+/actions/workflows/[^/]+/runs", load("runs_success.json"))
    return fake


def search_items(replace):
    """Fixture items with per-number replacements, e.g. {15251: {...}}."""
    items = copy.deepcopy(SEARCH["items"])
    for it in items:
        if it["number"] in replace:
            it.update(replace[it["number"]])
    return items


# ---------------------------------------------------------------- helpers
@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    shutil.copytree(DATA, d)
    return d


def run_cli(tmp_path, monkeypatch, fake, *extra, readme_text=README_TMPL, data=None,
            token=TOKEN, out=None, readme=None):
    readme = readme or (tmp_path / "README.md")
    if not readme.exists() or readme_text is not None:
        readme.write_text(readme_text if readme_text is not None else README_TMPL, encoding="utf-8")
    monkeypatch.setenv("GITHUB_TOKEN", token)
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(time, "sleep", fake.sleep)
    argv = ["--readme", str(readme), "--data-dir", str(data or DATA), *extra]
    if out is not None:
        argv += ["--out", str(out)]
    code = up.main(argv)
    return code, readme


def make_good(tmp_path, monkeypatch):
    """A README holding a successfully generated pair of blocks."""
    code, readme = run_cli(tmp_path, monkeypatch, default_fake())
    assert code == 0
    return readme


def block_lines(path_or_text, name):
    text = path_or_text.read_text() if isinstance(path_or_text, Path) else path_or_text
    return up.existing_block_lines(text, name)


# ================================================================ happy path
def test_happy_path_rows_notes_and_status(tmp_path, monkeypatch, capsys):
    fake = default_fake()
    code, readme = run_cli(tmp_path, monkeypatch, fake)
    out = capsys.readouterr().out
    assert code == 0
    text = readme.read_text()
    merged = block_lines(text, "MERGED-UPSTREAM")
    assert len(merged) == 6
    joined = "\n".join(merged)
    assert "openapi-generator" not in joined            # explicit exclusion
    assert "example-org" not in joined                   # not on the allowlist
    assert merged[0].startswith("- [future-agi/future-agi #1327](https://github.com/future-agi/future-agi/pull/1327): ")
    assert merged[-1].startswith(
        "- [langchain-ai/langchain #15251](https://github.com/langchain-ai/langchain/pull/15251): ")
    notes = json.loads((DATA / "pr-notes.json").read_text())
    for line in merged:
        repo, num = up.validate_merged_row(line)
        assert line.endswith(": " + notes[f"{repo}#{num}"])
        assert "`" not in line                           # notes win over titles
    flags = block_lines(text, "FLAGSHIPS")
    assert flags[:2] == [up.FLAG_HEADER, up.FLAG_SEPARATOR]
    assert len(flags) == 6
    for line in flags[2:]:
        assert line.count("|") == 4 and line.endswith("| passing |")
    # text outside the markers is untouched
    assert text.replace(text[text.index(START_F):text.index(END_F)], "") .count("Hand-written") == 2
    assert f"api calls: {len(fake.calls)}" in out
    assert TOKEN not in out and BODY_SENTINEL not in out


def test_query_and_request_shape(tmp_path, monkeypatch):
    fake = default_fake()
    run_cli(tmp_path, monkeypatch, fake)
    path, q = next(c for c in fake.calls if c[0] == "/search/issues")
    assert q["q"] == ["is:pr is:merged is:public author:gitchrisqueen -user:gitchrisqueen "
                      "-org:christopherqueenconsulting"]
    assert q["per_page"] == ["100"] and q["page"] == ["1"]
    assert set(fake.auth_headers) == {f"Bearer {TOKEN}"}
    runs = [c for c in fake.calls if c[0].endswith("/runs")]
    assert len(runs) == 4 and all(c[1]["status"] == ["completed"] for c in runs)
    cpcc = next(c for c in runs if "cpcc_task_automation" in c[0])
    assert cpcc[1]["branch"] == ["master"]


def test_second_run_is_idempotent(tmp_path, monkeypatch, capsys):
    readme = make_good(tmp_path, monkeypatch)
    first = readme.read_bytes()
    code, _ = run_cli(tmp_path, monkeypatch, default_fake(), readme_text=None)
    assert code == 0 and readme.read_bytes() == first
    assert "no change" in capsys.readouterr().out


def test_out_path_leaves_readme_untouched(tmp_path, monkeypatch):
    out = tmp_path / "sub" / "out.md"
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(), out=out)
    assert code == 0
    assert readme.read_text() == README_TMPL
    assert START_M in out.read_text() and len(block_lines(out, "MERGED-UPSTREAM")) == 6


def test_dry_run_in_place_writes_nothing(tmp_path, monkeypatch, capsys):
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(), "--dry-run")
    assert code == 0 and readme.read_text() == README_TMPL
    assert "dry run" in capsys.readouterr().out


def test_dry_run_still_writes_separate_out(tmp_path, monkeypatch):
    out = tmp_path / "preview.md"
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(), "--dry-run", out=out)
    assert code == 0 and readme.read_text() == README_TMPL and out.exists()


# ================================================================ token gate
def test_missing_token_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    readme = tmp_path / "README.md"
    readme.write_text(README_TMPL)
    assert up.main(["--readme", str(readme), "--data-dir", str(DATA)]) == 2
    assert readme.read_text() == README_TMPL


def test_non_ghs_token_refused_without_network(tmp_path, monkeypatch):
    fake = default_fake()
    code, readme = run_cli(tmp_path, monkeypatch, fake, token="gho_" + "x" * 20)
    assert code == 2 and fake.calls == [] and readme.read_text() == README_TMPL


def test_non_ghs_allowed_with_flag(tmp_path, monkeypatch):
    code, _ = run_cli(tmp_path, monkeypatch, default_fake(), "--allow-non-ghs", token="gho_" + "x" * 20)
    assert code == 0


# ================================================================ HTTP failures
def failing_search(response):
    fake = default_fake()
    fake.override(r"/search/issues", response)
    return fake


@pytest.mark.parametrize("status", [401, 403, 404, 500, 502, 503])
def test_search_http_errors_keep_last_good(tmp_path, monkeypatch, capsys, status):
    good = make_good(tmp_path, monkeypatch)
    before = good.read_bytes()
    capsys.readouterr()
    code, _ = run_cli(tmp_path, monkeypatch, failing_search(Err(status)), readme_text=None)
    out = capsys.readouterr()
    assert code == 1
    assert good.read_bytes() == before
    assert BODY_SENTINEL not in out.out + out.err and HEADER_SENTINEL not in out.out + out.err
    assert "FAILED" in out.out


def test_401_is_not_retried(tmp_path, monkeypatch):
    fake = failing_search(Err(401))
    run_cli(tmp_path, monkeypatch, fake)
    assert fake.count(r"/search/issues") == 1 and fake.sleeps == []


def test_403_without_rate_signal_is_not_retried(tmp_path, monkeypatch):
    fake = failing_search(Err(403))
    code, _ = run_cli(tmp_path, monkeypatch, fake)
    assert code == 1 and fake.count(r"/search/issues") == 1 and fake.sleeps == []


def test_429_retry_after_then_success(tmp_path, monkeypatch):
    fake = failing_search(Seq(Err(429, {"Retry-After": "2"}), paged_search(copy.deepcopy(SEARCH["items"]))))
    code, _ = run_cli(tmp_path, monkeypatch, fake)
    assert code == 0 and fake.sleeps == [2.0] and fake.count(r"/search/issues") == 2


def test_403_retry_after_is_honoured(tmp_path, monkeypatch):
    fake = failing_search(Seq(Err(403, {"Retry-After": "7"}), paged_search(copy.deepcopy(SEARCH["items"]))))
    code, _ = run_cli(tmp_path, monkeypatch, fake)
    assert code == 0 and fake.sleeps == [7.0]


def test_403_rate_limit_reset_header(tmp_path, monkeypatch):
    hdr = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(time.time()) + 5)}
    fake = failing_search(Seq(Err(403, hdr), paged_search(copy.deepcopy(SEARCH["items"]))))
    code, _ = run_cli(tmp_path, monkeypatch, fake)
    assert code == 0 and len(fake.sleeps) == 1 and 1.0 <= fake.sleeps[0] <= 6.0


def test_retry_after_too_long_fails_without_sleeping(tmp_path, monkeypatch):
    fake = failing_search(Err(429, {"Retry-After": "3600"}))
    code, _ = run_cli(tmp_path, monkeypatch, fake)
    assert code == 1 and fake.sleeps == [] and fake.count(r"/search/issues") == 1


def test_persistent_429_stops_after_three_attempts(tmp_path, monkeypatch):
    fake = failing_search(Err(429, {"Retry-After": "1"}))
    code, _ = run_cli(tmp_path, monkeypatch, fake)
    assert code == 1 and fake.count(r"/search/issues") == 3 and fake.sleeps == [1.0, 1.0]


def test_5xx_then_success(tmp_path, monkeypatch):
    fake = failing_search(Seq(Err(502), Err(503), paged_search(copy.deepcopy(SEARCH["items"]))))
    code, _ = run_cli(tmp_path, monkeypatch, fake)
    assert code == 0 and fake.count(r"/search/issues") == 3 and len(fake.sleeps) == 2


def test_persistent_5xx_fails_after_three_attempts(tmp_path, monkeypatch):
    fake = failing_search(Err(500))
    code, _ = run_cli(tmp_path, monkeypatch, fake)
    assert code == 1 and fake.count(r"/search/issues") == 3


@pytest.mark.parametrize("exc", [
    TimeoutError("t"),
    socket.timeout("t"),
    urllib.error.URLError(socket.timeout("t")),
    urllib.error.URLError("name resolution"),
    ConnectionResetError("reset"),
])
def test_timeouts_and_network_errors(tmp_path, monkeypatch, exc):
    good = make_good(tmp_path, monkeypatch)
    before = good.read_bytes()
    fake = failing_search(exc)
    code, _ = run_cli(tmp_path, monkeypatch, fake, readme_text=None)
    assert code == 1 and good.read_bytes() == before and fake.count(r"/search/issues") == 3


def test_timeout_then_success(tmp_path, monkeypatch):
    fake = failing_search(Seq(TimeoutError("t"), paged_search(copy.deepcopy(SEARCH["items"]))))
    code, _ = run_cli(tmp_path, monkeypatch, fake)
    assert code == 0 and len(fake.sleeps) == 1


def test_bad_json_and_bad_redirect_target(tmp_path, monkeypatch):
    class Raw(FakeGitHub):
        def __call__(self, req, timeout=None):
            if "/search/issues" in req.full_url:
                return FakeResp(b"not json", req.full_url)
            return super().__call__(req, timeout)

    good = make_good(tmp_path, monkeypatch)
    before = good.read_bytes()
    fake = Raw()
    fake.route(r"/repos/[^/]+/[^/]+", repo_handler)
    fake.route(r"/repos/[^/]+/[^/]+/actions/workflows/[^/]+/runs", load("runs_success.json"))
    code, _ = run_cli(tmp_path, monkeypatch, fake, readme_text=None)
    assert code == 1 and good.read_bytes() == before

    class Redirected(FakeGitHub):
        def __call__(self, req, timeout=None):
            if "/search/issues" in req.full_url:
                return FakeResp(json.dumps(SEARCH).encode(), "https://evil.example/search")
            return super().__call__(req, timeout)

    fake = Redirected()
    fake.route(r"/repos/[^/]+/[^/]+", repo_handler)
    fake.route(r"/repos/[^/]+/[^/]+/actions/workflows/[^/]+/runs", load("runs_success.json"))
    code, _ = run_cli(tmp_path, monkeypatch, fake, readme_text=None)
    assert code == 1 and good.read_bytes() == before


# ================================================================ search semantics
def test_incomplete_results_true_fails(tmp_path, monkeypatch):
    good = make_good(tmp_path, monkeypatch)
    before = good.read_bytes()
    bad = copy.deepcopy(SEARCH)
    bad["incomplete_results"] = True
    code, _ = run_cli(tmp_path, monkeypatch, failing_search(bad), readme_text=None)
    assert code == 1 and good.read_bytes() == before


def test_incomplete_results_missing_fails(tmp_path, monkeypatch):
    good = make_good(tmp_path, monkeypatch)
    before = good.read_bytes()
    bad = {"total_count": 8, "items": SEARCH["items"]}
    code, _ = run_cli(tmp_path, monkeypatch, failing_search(bad), readme_text=None)
    assert code == 1 and good.read_bytes() == before


def test_empty_result_fails_and_keeps_block(tmp_path, monkeypatch, capsys):
    good = make_good(tmp_path, monkeypatch)
    before = good.read_bytes()
    code, _ = run_cli(tmp_path, monkeypatch, default_fake(items=[]), readme_text=None)
    assert code == 1 and good.read_bytes() == before
    assert "empty result" in capsys.readouterr().out


def test_empty_result_on_fresh_block_still_fails(tmp_path, monkeypatch):
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(items=[]))
    assert code == 1
    assert block_lines(readme, "MERGED-UPSTREAM") == []           # nothing invented
    assert len(block_lines(readme, "FLAGSHIPS")) == 6              # good block still written


def test_shrunken_result_fails_and_keeps_block(tmp_path, monkeypatch, capsys):
    good = make_good(tmp_path, monkeypatch)
    before = good.read_bytes()
    fewer = [it for it in SEARCH["items"] if it["number"] != 1327]
    code, _ = run_cli(tmp_path, monkeypatch, default_fake(items=fewer), readme_text=None)
    assert code == 1 and good.read_bytes() == before
    assert "shrunken result" in capsys.readouterr().out


def test_pagination_reads_every_page(tmp_path, monkeypatch):
    junk = [{"number": i, "title": "filler", "repository_url": "https://api.github.com/repos/example-org/example-repo",
             "user": {"login": "gitchrisqueen"}, "pull_request": {"merged_at": "2026-01-01T00:00:00Z"}}
            for i in range(1, 145)]
    items = junk + copy.deepcopy(SEARCH["items"])           # 152 results over two pages
    fake = default_fake(items=items)
    code, readme = run_cli(tmp_path, monkeypatch, fake)
    assert code == 0 and len(block_lines(readme, "MERGED-UPSTREAM")) == 6
    pages = [q["page"][0] for p, q in fake.calls if p == "/search/issues"]
    assert pages == ["1", "2"]
    assert all(q["per_page"] == ["100"] for p, q in fake.calls if p == "/search/issues")


def test_pagination_short_second_page_fails(tmp_path, monkeypatch):
    items = copy.deepcopy(SEARCH["items"]) * 13                    # 104 items served, total claims 150
    fake = default_fake()
    fake.override(r"/search/issues", paged_search(items, total=150))
    good = make_good(tmp_path, monkeypatch)
    before = good.read_bytes()
    code, _ = run_cli(tmp_path, monkeypatch, fake, readme_text=None)
    assert code == 1 and good.read_bytes() == before


@pytest.mark.parametrize("total", [900, 950, 1000])
def test_total_count_near_search_cap_hard_fails(tmp_path, monkeypatch, total):
    good = make_good(tmp_path, monkeypatch)
    before = good.read_bytes()
    fake = default_fake()
    fake.override(r"/search/issues", paged_search(copy.deepcopy(SEARCH["items"]), total=total))
    code, _ = run_cli(tmp_path, monkeypatch, fake, readme_text=None)
    assert code == 1 and good.read_bytes() == before and fake.count(r"/search/issues") == 1


# ================================================================ privacy and allowlist
def test_private_flag_on_result_row_fails_with_no_output(tmp_path, monkeypatch, capsys):
    items = search_items({644: {"private": True}})
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(items=items))
    assert code == 1
    assert block_lines(readme, "MERGED-UPSTREAM") == []
    text = readme.read_text()
    assert "google_workspace_mcp" not in text
    assert "marked private" in capsys.readouterr().out


def test_private_nested_repository_flag_fails(tmp_path, monkeypatch):
    items = search_items({418: {"repository": {"private": True}}})
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(items=items))
    assert code == 1 and block_lines(readme, "MERGED-UPSTREAM") == []


def test_private_repo_on_recheck_fails_with_no_output(tmp_path, monkeypatch):
    fake = default_fake()
    private = copy.deepcopy(REPO_TEMPLATE)
    private.update({"full_name": "Martian-Engineering/lossless-claw", "private": True})
    fake.override(r"/repos/Martian-Engineering/lossless-claw", private)
    code, readme = run_cli(tmp_path, monkeypatch, fake)
    assert code == 1
    assert block_lines(readme, "MERGED-UPSTREAM") == []
    assert "lossless-claw" not in readme.read_text()


def test_private_missing_field_is_not_treated_as_public(tmp_path, monkeypatch):
    fake = default_fake()
    fake.override(r"/repos/future-agi/future-agi", {"full_name": "future-agi/future-agi"})
    code, readme = run_cli(tmp_path, monkeypatch, fake)
    assert code == 1 and block_lines(readme, "MERGED-UPSTREAM") == []


def test_repo_recheck_name_mismatch_fails(tmp_path, monkeypatch):
    fake = default_fake()
    other = copy.deepcopy(REPO_TEMPLATE)
    other["full_name"] = "someone-else/other"
    fake.override(r"/repos/langchain-ai/langchain", other)
    code, readme = run_cli(tmp_path, monkeypatch, fake)
    assert code == 1 and block_lines(readme, "MERGED-UPSTREAM") == []


def test_allowlist_is_enforced(tmp_path, monkeypatch, data_dir):
    al = json.loads((data_dir / "allowlist.json").read_text())
    al["merged_upstream"].remove("future-agi/future-agi")
    (data_dir / "allowlist.json").write_text(json.dumps(al))
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(), data=data_dir)
    # future-agi is dropped, so only five rows; and that is not "shrunken" on a fresh block
    assert code == 0
    lines = block_lines(readme, "MERGED-UPSTREAM")
    assert len(lines) == 5 and not any("future-agi" in ln for ln in lines)


def test_excluded_pr_is_dropped_even_if_repo_were_allowlisted(tmp_path, monkeypatch, data_dir):
    al = json.loads((data_dir / "allowlist.json").read_text())
    al["merged_upstream"].append("OpenAPITools/openapi-generator")
    (data_dir / "allowlist.json").write_text(json.dumps(al))
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(), data=data_dir)
    assert code == 0 and "openapi-generator" not in readme.read_text()


def test_unmerged_or_foreign_author_rows_are_skipped(tmp_path, monkeypatch):
    items = search_items({
        644: {"pull_request": {"merged_at": None}},
        418: {"user": {"login": "someone-else"}},
    })
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(items=items))
    assert code == 0
    joined = "\n".join(block_lines(readme, "MERGED-UPSTREAM"))
    assert "#644" not in joined and "#418" not in joined and len(block_lines(readme, "MERGED-UPSTREAM")) == 4


@pytest.mark.parametrize("bad_url", [
    "https://evil.example/repos/langchain-ai/langchain",
    "https://api.github.com/repos/langchain-ai/langchain/../x",
    "https://api.github.com/repos/lang chain/x",
    "http://api.github.com/repos/langchain-ai/langchain",
])
def test_bad_repository_url_in_result_is_skipped(tmp_path, monkeypatch, bad_url):
    items = search_items({15251: {"repository_url": bad_url}})
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(items=items))
    assert code == 0 and "#15251" not in readme.read_text()


# ================================================================ flagships
def flagship_fake(**overrides):
    fake = default_fake()
    for pattern, response in overrides.items():
        fake.override(pattern, response)
    return fake


CPCC = r"/repos/christopherqueenconsulting/cpcc_task_automation"
CPCC_RUNS = CPCC + r"/actions/workflows/unit-tests\.yml/runs"


def status_of(readme, repo_fragment):
    for line in block_lines(readme, "FLAGSHIPS")[2:]:
        if repo_fragment in line:
            return line.rsplit("| ", 1)[1].rstrip(" |")
    raise AssertionError("row missing")


def test_flagship_404_is_unavailable(tmp_path, monkeypatch):
    code, readme = run_cli(tmp_path, monkeypatch, flagship_fake(**{CPCC: Err(404)}))
    assert code == 0 and status_of(readme, "cpcc_task_automation") == "unavailable"
    assert status_of(readme, "hearing-copilot") == "passing"


def test_flagship_renamed_is_unavailable(tmp_path, monkeypatch):
    renamed = copy.deepcopy(REPO_TEMPLATE)
    renamed["full_name"] = "christopherqueenconsulting/cpcc_new_name"
    code, readme = run_cli(tmp_path, monkeypatch, flagship_fake(**{CPCC: renamed}))
    assert code == 0 and status_of(readme, "cpcc_task_automation") == "unavailable"
    assert "cpcc_new_name" not in readme.read_text()


def test_flagship_archived_is_unavailable(tmp_path, monkeypatch):
    arch = copy.deepcopy(REPO_TEMPLATE)
    arch.update({"full_name": "gitchrisqueen/panthera", "archived": True})
    code, readme = run_cli(tmp_path, monkeypatch, flagship_fake(**{r"/repos/gitchrisqueen/panthera": arch}))
    assert code == 0 and status_of(readme, "panthera") == "unavailable"


def test_flagship_workflow_404_is_unavailable(tmp_path, monkeypatch):
    code, readme = run_cli(tmp_path, monkeypatch, flagship_fake(**{CPCC_RUNS: Err(404)}))
    assert code == 0 and status_of(readme, "cpcc_task_automation") == "unavailable"


@pytest.mark.parametrize("fixture,expected", [
    ("runs_success.json", "passing"),
    ("runs_failure.json", "failing"),
    ("runs_cancelled_then_success.json", "passing"),
    ("runs_only_cancelled.json", "unavailable"),
    ("runs_empty.json", "unavailable"),
])
def test_flagship_status_from_default_branch_runs(tmp_path, monkeypatch, fixture, expected):
    code, readme = run_cli(tmp_path, monkeypatch, flagship_fake(**{CPCC_RUNS: load(fixture)}))
    assert code == 0 and status_of(readme, "cpcc_task_automation") == expected


def test_flagship_ignores_pull_request_and_other_branch_runs(tmp_path, monkeypatch):
    runs = {"workflow_runs": [
        {"event": "pull_request", "head_branch": "master", "conclusion": "failure"},
        {"event": "push", "head_branch": "feature", "conclusion": "failure"},
        {"event": "push", "head_branch": "master", "conclusion": "success"},
    ]}
    code, readme = run_cli(tmp_path, monkeypatch, flagship_fake(**{CPCC_RUNS: runs}))
    assert code == 0 and status_of(readme, "cpcc_task_automation") == "passing"


def test_flagship_private_repo_fails_the_block(tmp_path, monkeypatch):
    priv = copy.deepcopy(REPO_TEMPLATE)
    priv.update({"full_name": "gitchrisqueen/panthera", "private": True})
    code, readme = run_cli(tmp_path, monkeypatch, flagship_fake(**{r"/repos/gitchrisqueen/panthera": priv}))
    assert code == 1
    assert block_lines(readme, "FLAGSHIPS") == []
    assert len(block_lines(readme, "MERGED-UPSTREAM")) == 6          # the good block was still written


def test_flagship_server_error_keeps_last_good(tmp_path, monkeypatch):
    good = make_good(tmp_path, monkeypatch)
    before = good.read_bytes()
    code, _ = run_cli(tmp_path, monkeypatch, flagship_fake(**{CPCC_RUNS: Err(500)}), readme_text=None)
    assert code == 1 and good.read_bytes() == before


def test_flagship_failure_after_a_run_flips_nothing_else(tmp_path, monkeypatch):
    good = make_good(tmp_path, monkeypatch)
    code, _ = run_cli(tmp_path, monkeypatch, flagship_fake(**{CPCC_RUNS: load("runs_failure.json")}),
                      readme_text=None)
    assert code == 0 and status_of(good, "cpcc_task_automation") == "failing"


def test_flagship_name_with_pipe_fails_the_block(tmp_path, monkeypatch, data_dir):
    fl = json.loads((data_dir / "flagships.json").read_text())
    fl["flagships"][0]["name"] = "Name | with | pipes"
    (data_dir / "flagships.json").write_text(json.dumps(fl))
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(), data=data_dir)
    assert code == 1 and block_lines(readme, "FLAGSHIPS") == []


@pytest.mark.parametrize("field,value", [
    ("check", "see https://evil.example"), ("check", "line\nbreak"), ("name", "<b>bold</b>"),
    ("workflow", "../../etc/passwd"), ("repo", "gitchrisqueen/not-allowlisted"),
])
def test_flagship_data_validation(tmp_path, monkeypatch, data_dir, field, value):
    fl = json.loads((data_dir / "flagships.json").read_text())
    fl["flagships"][1][field] = value
    (data_dir / "flagships.json").write_text(json.dumps(fl))
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(), data=data_dir)
    assert code == 1 and block_lines(readme, "FLAGSHIPS") == []


def test_flagship_table_keeps_three_columns(tmp_path, monkeypatch):
    code, readme = run_cli(tmp_path, monkeypatch, default_fake())
    for line in block_lines(readme, "FLAGSHIPS"):
        assert len(line.strip("|").split("|")) == 3


# ================================================================ markers
def broken_readmes():
    both = README_TMPL
    return {
        "missing-merged-start": both.replace(START_M + "\n", ""),
        "missing-merged-end": both.replace(END_M + "\n", ""),
        "missing-flag-start": both.replace(START_F + "\n", ""),
        "missing-flag-end": both.replace(END_F + "\n", ""),
        "duplicate-merged-start": both.replace(START_M, START_M + "\n" + START_M),
        "duplicate-merged-end": both.replace(END_M, END_M + "\n" + END_M),
        "duplicate-flag-start": both.replace(START_F, START_F + "\n" + START_F),
        "end-before-start": both.replace(START_M + "\n" + END_M, END_M + "\n" + START_M),
        "inline-marker": both.replace(START_M, "text " + START_M),
        "marker-with-trailing-text": both.replace(END_M, END_M + " trailing"),
        "overlap": both.replace(START_M + "\n" + END_M, START_M + "\n" + START_F + "\n" + END_M),
        "no-markers": "# Just a title\n",
        "crlf": both.replace("\n", "\r\n"),
    }


@pytest.mark.parametrize("case", sorted(broken_readmes()))
def test_bad_markers_abort_without_writing(tmp_path, monkeypatch, case):
    text = broken_readmes()[case]
    fake = default_fake()
    code, readme = run_cli(tmp_path, monkeypatch, fake, readme_text=text)
    assert code != 0
    assert readme.read_bytes() == text.encode()
    assert fake.calls == []                                   # aborted before any request


def test_marker_abort_with_separate_out_writes_nothing(tmp_path, monkeypatch):
    out = tmp_path / "out.md"
    code, _ = run_cli(tmp_path, monkeypatch, default_fake(), readme_text=broken_readmes()["no-markers"], out=out)
    assert code != 0 and not out.exists()


def test_symlinked_readme_is_refused(tmp_path, monkeypatch):
    real = tmp_path / "real.md"
    real.write_text(README_TMPL)
    link = tmp_path / "README.md"
    link.symlink_to(real)
    code, _ = run_cli(tmp_path, monkeypatch, default_fake(), readme_text=None, readme=link)
    assert code == 2 and real.read_text() == README_TMPL


# ================================================================ fault injection
def test_inject_bad_allowlist_fails_merged_only(tmp_path, monkeypatch, capsys):
    fake = default_fake()
    code, readme = run_cli(tmp_path, monkeypatch, fake, "--inject-fault", "bad-allowlist")
    assert code == 1
    assert block_lines(readme, "MERGED-UPSTREAM") == []
    assert len(block_lines(readme, "FLAGSHIPS")) == 6          # the good block is still written
    assert fake.count(r"/search/issues") == 0                  # failed before the network
    assert "not a valid repo" not in readme.read_text()


def test_inject_bad_allowlist_keeps_last_good_merged(tmp_path, monkeypatch):
    good = make_good(tmp_path, monkeypatch)
    before = good.read_bytes()
    code, _ = run_cli(tmp_path, monkeypatch, default_fake(), "--inject-fault", "bad-allowlist", readme_text=None)
    assert code == 1 and good.read_bytes() == before


def test_inject_bad_marker_fails_flagships_only(tmp_path, monkeypatch):
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(), "--inject-fault", "bad-marker")
    assert code == 1
    assert block_lines(readme, "FLAGSHIPS") == []
    assert len(block_lines(readme, "MERGED-UPSTREAM")) == 6
    assert readme.read_text().count(START_F) == 1               # the corruption was never written


def test_inject_none_is_clean(tmp_path, monkeypatch):
    code, _ = run_cli(tmp_path, monkeypatch, default_fake(), "--inject-fault", "none")
    assert code == 0


def test_inject_fault_value_is_validated_by_argparse_and_inside(tmp_path):
    with pytest.raises(SystemExit) as exc:
        up.main(["--readme", str(tmp_path / "x.md"), "--inject-fault", "evil"])
    assert exc.value.code == 2
    ns = argparse.Namespace(inject_fault="evil", readme="x", out=None, data_dir="d", dry_run=False,
                            allow_non_ghs=False)
    with pytest.raises(up.FatalError):
        up.run(ns)


# ================================================================ sanitiser
HOSTILE = load("hostile_titles.json")


def hostile_run(tmp_path, monkeypatch, title, notes=None):
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    (data / "pr-notes.json").write_text(json.dumps(notes or {}))
    items = search_items({15251: {"title": title}})
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(items=items), data=data)
    return code, readme


@pytest.mark.parametrize("title", HOSTILE, ids=[f"h{i}" for i in range(len(HOSTILE))])
def test_hostile_titles_are_neutralised(tmp_path, monkeypatch, title):
    code, readme = hostile_run(tmp_path, monkeypatch, title)
    assert code == 0
    text = readme.read_text()
    lines = block_lines(text, "MERGED-UPSTREAM")
    assert len(lines) == 6                                     # a title can never add or split a line
    for line in lines:
        assert up.validate_merged_row(line) is not None
    row = next(ln for ln in lines if "#15251]" in ln)
    note = row.split("): ", 1)[1]
    assert note == "PR #15251" or (note.startswith("`") and note.endswith("`") and 1 <= len(note) - 2 <= 100)
    for needle in ("](http", "<", ">", "@", "!["):
        assert needle not in row.replace("](https://github.com/langchain-ai/langchain/pull/15251)", "")
    assert text.count(START_M) == 1 and text.count(END_M) == 1
    assert text.count(START_F) == 1 and text.count(END_F) == 1
    # the table keeps its shape
    for line in block_lines(text, "FLAGSHIPS"):
        assert line.count("|") == 4
    # the guard, run against the pre-run README, accepts the result
    base = tmp_path / "base.md"
    base.write_text(README_TMPL)
    assert gp.check(str(base), str(readme), str(DATA / "allowlist.json")) == []


@pytest.mark.parametrize("title,expected", [
    ("Fix the thing", "`Fix the thing`"),
    ("ends with newline\n", "`ends with newline`"),
    ("bidi ‮evil‬ title", "`bidi evil title`"),
    ("zero​width⁠ joiner", "`zerowidth joiner`"),
    ("fix(evals): add scroll (#1071)", "`fix(evals): add scroll (#1071)`"),
    ("a | b", "PR #15251"),
    ("see https://evil.example/x", "PR #15251"),
    ("see www.evil.example", "PR #15251"),
    ("[x](y)", "PR #15251"),
    ("<!-- MERGED-UPSTREAM:END -->", "PR #15251"),
    ("＜script＞", "PR #15251"),
    ("emoji \U0001f600", "PR #15251"),
    ("back\\slash", "PR #15251"),
    ("`tick`", "PR #15251"),
    ("", "PR #15251"),
    ("   \n  ", "PR #15251"),
    (None, "PR #15251"),
    (12345, "PR #15251"),
])
def test_title_fragment_exact(title, expected):
    assert up.title_fragment(title, 15251) == expected


def test_title_fragment_caps_length():
    frag = up.title_fragment("x" * 400, 7)
    assert frag == "`" + "x" * 97 + "...`" and len(frag) == 102


def test_title_with_url_scheme_survives_as_placeholder_not_text():
    assert "evil" not in up.title_fragment("go to http://evil.example now", 1)


def test_trailing_newline_never_passes_allowlist_regexes():
    for rx in (up.TITLE_RE, up.NOTE_RE, up.NAME_RE):
        assert rx.fullmatch("abc") and rx.fullmatch("abc\n") is None
    assert re.match(r"^[a-z]+$", "abc\n")                      # why fullmatch is used, not `$`
    assert up.note_fragment("good note\n") is None


def test_code_span_fence_is_longer_than_any_backtick_run():
    assert up.code_span("plain") == "`plain`"
    assert up.code_span("a`b") == "``a`b``"
    assert up.code_span("a``b```c") == "````a``b```c````"
    assert up.code_span("`edge") == "`` `edge ``"


def test_clean_text_normalises():
    assert up.clean_text("Ｈello world") == "Hello world"
    assert up.clean_text("a‮b​c\x00d\x1be") == "abcde"
    assert up.clean_text("a\r\n\tb") == "a b"
    assert up.clean_text(None) is None


@pytest.mark.parametrize("repo,ok", [
    ("owner/repo", True), ("Org-1/repo_name.x", True), ("a/b", True),
    ("owner/repo/extra", False), ("owner", False), ("own er/repo", False), ("../repo", False),
    ("owner/..", False), ("owner/repo\n", False), ("", False), ("a/" + "b" * 200, False), (None, False),
])
def test_repo_name_validation(repo, ok):
    assert up.valid_repo(repo) is ok


# ---- committed notes
def test_notes_override_title_and_bad_notes_fall_back(tmp_path, monkeypatch, data_dir):
    notes = {
        "langchain-ai/langchain#15251": "A plain note",
        "future-agi/future-agi#1327": "See https://evil.example",          # denied
        "Martian-Engineering/lossless-claw#418": "has www.evil.example",     # denied
        "PostHog/posthog-openclaw#15": "pipe | inside",                      # charset
        "PostHog/posthog-openclaw#35": "colon: inside",                      # charset
        "taylorwilsdon/google_workspace_mcp#644": "trailing newline\n",      # fullmatch
        "not a key": "ignored",
    }
    (data_dir / "pr-notes.json").write_text(json.dumps(notes))
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(), data=data_dir)
    assert code == 0
    rows = {up.validate_merged_row(ln): ln for ln in block_lines(readme, "MERGED-UPSTREAM")}
    assert rows[("langchain-ai/langchain", 15251)].endswith(": A plain note")
    for key in (("future-agi/future-agi", 1327), ("Martian-Engineering/lossless-claw", 418),
                ("PostHog/posthog-openclaw", 15), ("PostHog/posthog-openclaw", 35),
                ("taylorwilsdon/google_workspace_mcp", 644)):
        note = rows[key].split("): ", 1)[1]
        assert note.startswith("`") or note.startswith("PR #")       # title fallback


def test_notes_keys_match_case_insensitively(tmp_path, monkeypatch, data_dir):
    (data_dir / "pr-notes.json").write_text(json.dumps({"LANGCHAIN-AI/LANGCHAIN#15251": "Cased key"}))
    code, readme = run_cli(tmp_path, monkeypatch, default_fake(), data=data_dir)
    assert code == 0 and any(ln.endswith(": Cased key") for ln in block_lines(readme, "MERGED-UPSTREAM"))


def test_notes_longer_than_limit_rejected():
    assert up.note_fragment("x" * 140) == "x" * 140
    assert up.note_fragment("x" * 141) is None


def test_committed_data_files_are_valid():
    allow = up.load_allowlist(str(DATA))
    assert len(allow.merged) == 5 and len(allow.flagships) == 4
    assert ("openapitools/openapi-generator", 17483) in allow.excluded
    notes, rejected = up.load_notes(str(DATA))
    assert rejected == 0 and len(notes) == 6
    fl = up.load_flagships(str(DATA), allow)
    assert [e["repo"] for e in fl] == [
        "christopherqueenconsulting/linkedin_engagement_manager",
        "christopherqueenconsulting/cpcc_task_automation",
        "gitchrisqueen/hearing-copilot",
        "gitchrisqueen/panthera"]
    for e in fl:
        assert 3 <= len(e["check"].split()) <= 6


# ================================================================ output hygiene and structure
def test_no_response_body_or_header_ever_printed(tmp_path, monkeypatch, capsys):
    for response in (Err(500), Err(403), Err(429, {"Retry-After": "1"})):
        run_cli(tmp_path, monkeypatch, failing_search(response))
    cap = capsys.readouterr()
    for secret in (BODY_SENTINEL, HEADER_SENTINEL, TOKEN):
        assert secret not in cap.out and secret not in cap.err


def test_unexpected_exception_does_not_print_its_message(tmp_path, monkeypatch, capsys):
    fake = failing_search(RuntimeError("LEAK-" + TOKEN))
    code, _ = run_cli(tmp_path, monkeypatch, fake)
    cap = capsys.readouterr()
    assert code == 1 and "LEAK" not in cap.out + cap.err and "unexpected" in cap.out


def test_generator_has_no_git_or_subprocess_use():
    src = (ROOT / "scripts" / "update_profile.py").read_text()
    for needle in ("subprocess", "os.system", "git push", "--force", "os.popen", "re.sub("):
        assert needle not in src


def test_row_grammar_is_identical_in_generator_and_guard():
    for name in ("REPO_RE", "TITLE_RE", "NOTE_RE", "NAME_RE", "MERGED_ROW_RE", "FLAG_ROW_RE"):
        assert getattr(up, name).pattern == getattr(gp, name).pattern, name
    assert up.FLAG_HEADER == gp.FLAG_HEADER and up.FLAG_SEPARATOR == gp.FLAG_SEPARATOR
    assert up.DENIED_SUBSTRINGS == gp.DENIED_SUBSTRINGS
    samples = [
        "- [a/b #1](https://github.com/a/b/pull/1): PR #1",
        "- [a/b #1](https://github.com/a/b/pull/1): `Some title`",
        "- [a/b #1](https://github.com/a/b/pull/2): note",
        "- [a/b #1](https://github.com/c/d/pull/1): note",
        "- [a/b #1](https://evil.example/a/b/pull/1): note",
        "- [a/b #1](https://github.com/a/b/pull/1): note https://x.y",
        "- [a/b #01](https://github.com/a/b/pull/01): note",
        "* [a/b #1](https://github.com/a/b/pull/1): note",
        "- [a/b #1](https://github.com/a/b/pull/1): ",
        "- [a/b #1](https://github.com/a/b/pull/1): `` ",
    ]
    for s in samples:
        assert (up.validate_merged_row(s) is not None) == (gp.merged_row(s) is not None), s
    flag_samples = [
        "| [N](https://github.com/a/b) | check text | passing |",
        "| [N](https://github.com/a/b) | check text | great |",
        "| [N](https://evil.example/a/b) | check text | passing |",
        "| [N | x](https://github.com/a/b) | check | passing |",
    ]
    for s in flag_samples:
        assert (up.validate_flagship_row(s) is not None) == (gp.flagship_row(s) is not None), s


def test_splice_helpers_never_use_regex_substitution_with_data():
    out = up.splice(README_TMPL, "MERGED-UPSTREAM", [r"- \1 \g<0> $& \\"])
    assert r"- \1 \g<0> $& \\" in out
