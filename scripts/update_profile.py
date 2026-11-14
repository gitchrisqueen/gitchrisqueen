#!/usr/bin/env python3
"""Regenerate the two generated blocks of the profile README.

Blocks (each between exactly one START and one END marker line):
  <!-- MERGED-UPSTREAM:START --> ... <!-- MERGED-UPSTREAM:END -->
  <!-- FLAGSHIPS:START -->       ... <!-- FLAGSHIPS:END -->

Data comes from the public GitHub REST API with GITHUB_TOKEN only. Standard
library only (Python 3.11). The script never calls git and never prints
response bodies, headers, or the token.

Exit codes: 0 every block succeeded; 1 at least one block failed (the good
blocks were still written, a failed block keeps its last good content);
2 usage, token, file, or README-structure error (nothing written).

Fault injection (--inject-fault, re-validated inside):
  bad-allowlist  adds a malformed entry to the allowlist the merged block
                 reads, so that block fails validation before any network call.
  bad-marker     corrupts the marker structure the flagships block splices
                 into, so that block fails at the splice step.
In both cases the other block is still written and the run exits 1.

Shrinking (--allow-shrink): by default the merged block may never end up with
fewer rows than the README already holds, which fails the block closed. The
flag turns that one check off so a reviewed commit can deliberately remove a
row (see docs/MAINTENANCE.md). The scheduled workflows never pass it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

API_ROOT = "https://api.github.com"
USER_AGENT = "profile-readme-generator"
API_VERSION = "2022-11-28"

FAULTS = ("none", "bad-allowlist", "bad-marker")

MAX_ATTEMPTS = 3          # per request (first try plus retries)
MAX_WAIT_SECONDS = 60     # longest Retry-After / reset wait we will honour
REQUEST_TIMEOUT = 20
MAX_RESPONSE_BYTES = 5_000_000
MAX_README_BYTES = 2_000_000
MAX_DATA_BYTES = 200_000
SEARCH_PAGE_SIZE = 100
SEARCH_MAX_PAGES = 10
SEARCH_NEAR_LIMIT = 900   # the search API serves at most 1000 results

# --- grammar (mirrored byte for byte in guard_publish.py; a test enforces it)
REPO_PART = r"[A-Za-z0-9._-]+"
REPO_RE = re.compile(rf"{REPO_PART}/{REPO_PART}")
NUM = r"[1-9][0-9]{0,9}"
TITLE_RE = re.compile(r"[A-Za-z0-9 .,:;()'/_+#-]{1,100}")
NOTE_RE = re.compile(r"[A-Za-z0-9 .,()'/+#-]{1,140}")
NAME_RE = re.compile(r"[A-Za-z0-9 .,()'/+#-]{1,60}")
NAME_CLASS = r"[A-Za-z0-9 .,()'/+#-]"
MERGED_ROW_RE = re.compile(
    rf"- \[(?P<repo>{REPO_PART}/{REPO_PART}) #(?P<num>{NUM})\]"
    rf"\(https://github\.com/(?P<lrepo>{REPO_PART}/{REPO_PART})/pull/(?P<lnum>{NUM})\): "
    r"(?P<note>.+)"
)
FLAG_HEADER = "| Repo | Check | Status |"
FLAG_SEPARATOR = "| --- | --- | --- |"
FLAG_ROW_RE = re.compile(
    rf"\| \[(?P<name>{NAME_CLASS}{{1,60}})\]\(https://github\.com/(?P<repo>{REPO_PART}/{REPO_PART})\)"
    rf" \| (?P<check>{NAME_CLASS}{{1,60}}) \| (?P<status>passing|failing|unavailable) \|"
)
STATUSES = ("passing", "failing", "unavailable")
DENIED_SUBSTRINGS = ("://", "www.", "<!--", "-->", "](", "<", ">")

BLOCK_MERGED = "MERGED-UPSTREAM"
BLOCK_FLAGSHIPS = "FLAGSHIPS"
BLOCK_NAMES = (BLOCK_MERGED, BLOCK_FLAGSHIPS)

NAME_FIELD_RE = re.compile(r"[A-Za-z0-9-]{1,39}")
WORKFLOW_FILE_RE = re.compile(r"[A-Za-z0-9._-]{1,100}\.ya?ml")
BRANCH_RE = re.compile(r"[A-Za-z0-9._/-]{1,100}")
EXCLUDED_PR_RE = re.compile(rf"({REPO_PART}/{REPO_PART})#({NUM})")
NOTE_KEY_RE = re.compile(rf"({REPO_PART}/{REPO_PART})#({NUM})")


class BlockError(Exception):
    """A block could not be generated. The message is ours, never third-party text."""


class ApiError(BlockError):
    def __init__(self, kind: str, status: int | None = None):
        self.kind = kind
        self.status = status
        super().__init__(kind if status is None else f"{kind} (HTTP {status})")


class FatalError(Exception):
    """Usage, token, file or README-structure problem: exit 2, write nothing."""


# --------------------------------------------------------------------------
# sanitiser
# --------------------------------------------------------------------------

def marker_start(name: str) -> str:
    return f"<!-- {name}:START -->"


def marker_end(name: str) -> str:
    return f"<!-- {name}:END -->"


def valid_repo(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 140:
        return False
    if not REPO_RE.fullmatch(value):
        return False
    return all(part.strip(".") for part in value.split("/"))


def clean_text(value: object) -> str | None:
    """NFKC, whitespace to single spaces, control/format/bidi/zero-width removed."""
    if not isinstance(value, str):
        return None
    text = unicodedata.normalize("NFKC", value[:2000])
    out = []
    for ch in text:
        if ch.isspace():
            out.append(" ")
        elif unicodedata.category(ch)[0] == "C":
            continue
        else:
            out.append(ch)
    return " ".join("".join(out).split())


def has_denied(text: str) -> bool:
    low = text.lower()
    return any(item in low for item in DENIED_SUBSTRINGS)


def code_span(text: str) -> str:
    """Wrap text in a code span whose fence is longer than any backtick run in it."""
    runs = re.findall(r"`+", text)
    fence = "`" * (max(len(r) for r in runs) + 1 if runs else 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def placeholder(number: int) -> str:
    return f"PR #{number}"


def title_fragment(raw_title: object, number: int) -> str:
    """Markdown for a third-party PR title: a code span, or the placeholder."""
    text = clean_text(raw_title)
    if not text:
        return placeholder(number)
    if len(text) > 100:
        text = text[:97].rstrip() + "..."
    if not TITLE_RE.fullmatch(text) or has_denied(text):
        return placeholder(number)
    return code_span(text)


def note_fragment(raw_note: object) -> str | None:
    """A committed note, or None if it fails the allowlist (caller falls back)."""
    if not isinstance(raw_note, str):
        return None
    text = unicodedata.normalize("NFKC", raw_note)
    if text != text.strip() or not NOTE_RE.fullmatch(text) or has_denied(text):
        return None
    return text


def validate_merged_row(line: str) -> tuple[str, int] | None:
    """Return (repo, number) if the line matches the merged-row grammar, else None."""
    m = MERGED_ROW_RE.fullmatch(line)
    if not m:
        return None
    repo, num = m.group("repo"), m.group("num")
    if m.group("lrepo") != repo or m.group("lnum") != num or not valid_repo(repo):
        return None
    note = m.group("note")
    if note.startswith("`") and note.endswith("`") and len(note) > 2:
        inner = note[1:-1]
        ok = inner == inner.strip() and TITLE_RE.fullmatch(inner) and not has_denied(inner)
    else:
        ok = NOTE_RE.fullmatch(note) and note == note.strip() and not has_denied(note)
    return (repo, int(num)) if ok else None


def validate_flagship_row(line: str) -> tuple[str, str] | None:
    """Return (repo, status) if the line matches the flagship-row grammar, else None."""
    m = FLAG_ROW_RE.fullmatch(line)
    if not m or not valid_repo(m.group("repo")):
        return None
    for key in ("name", "check"):
        value = m.group(key)
        if value != value.strip() or has_denied(value):
            return None
    return m.group("repo"), m.group("status")


# --------------------------------------------------------------------------
# GitHub client
# --------------------------------------------------------------------------

def _header_number(headers: object, name: str) -> float | None:
    try:
        raw = headers.get(name)  # type: ignore[attr-defined]
    except Exception:
        return None
    if raw is None:
        return None
    try:
        value = float(str(raw).strip())
    except ValueError:
        return None
    return value if value >= 0 else None


class ApiRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only when its target is under the API root.

    urllib copies request headers (Authorization included) onto the redirected
    request, so a redirect to another host would forward the token. Any target
    that does not start with API_ROOT + "/" is refused before it is requested.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not isinstance(newurl, str) or not newurl.startswith(API_ROOT + "/"):
            raise ApiError("bad-redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def make_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(ApiRedirectHandler)


class GitHubClient:
    def __init__(self, token: str, *, timeout: int = REQUEST_TIMEOUT,
                 max_attempts: int = MAX_ATTEMPTS, max_wait: int = MAX_WAIT_SECONDS):
        self._token = token
        # urlopen() uses the installed opener, so every request goes through
        # the redirect guard above.
        urllib.request.install_opener(make_opener())
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.max_wait = max_wait
        self.calls = 0

    def get_json(self, path: str, params: dict | None = None):
        url = API_ROOT + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        attempt = 0
        while True:
            attempt += 1
            self.calls += 1
            retry_wait: float | None = None
            failure: ApiError
            try:
                req = urllib.request.Request(url, method="GET", headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": API_VERSION,
                    "User-Agent": USER_AGENT,
                })
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    status = resp.getcode()
                    final = resp.geturl() if hasattr(resp, "geturl") else url
                    raw = resp.read(MAX_RESPONSE_BYTES + 1)
                if not isinstance(final, str) or not final.startswith(API_ROOT + "/"):
                    raise ApiError("bad-redirect")
                if status != 200:
                    raise ApiError("unexpected-status", status)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ApiError("response-too-large")
                try:
                    return json.loads(raw)
                except ValueError:
                    raise ApiError("bad-json") from None
            except urllib.error.HTTPError as exc:
                status = exc.code
                headers = exc.headers
                try:
                    exc.close()
                except Exception:
                    pass
                if status == 404:
                    raise ApiError("not-found", 404) from None
                if status == 401:
                    raise ApiError("unauthorized", 401) from None
                if status in (403, 429):
                    retry_after = _header_number(headers, "Retry-After")
                    remaining = None
                    try:
                        remaining = headers.get("X-RateLimit-Remaining")
                    except Exception:
                        pass
                    limited = status == 429 or retry_after is not None or str(remaining).strip() == "0"
                    if not limited:
                        raise ApiError("forbidden", status) from None
                    if retry_after is not None:
                        wait = retry_after
                    else:
                        reset = _header_number(headers, "X-RateLimit-Reset")
                        wait = max(1.0, reset - time.time()) if reset is not None else 5.0
                    if wait > self.max_wait:
                        raise ApiError("rate-limited-too-long", status) from None
                    failure = ApiError("rate-limited", status)
                    retry_wait = wait
                elif 500 <= status < 600:
                    failure = ApiError("server-error", status)
                    retry_wait = min(2.0 ** attempt, 10.0)
                else:
                    raise ApiError("http-error", status) from None
            except ApiError:
                raise
            except (TimeoutError, socket.timeout):
                failure = ApiError("timeout")
                retry_wait = min(2.0 ** attempt, 10.0)
            except urllib.error.URLError as exc:
                reason = exc.reason
                kind = "timeout" if isinstance(reason, (TimeoutError, socket.timeout)) else "network-error"
                failure = ApiError(kind)
                retry_wait = min(2.0 ** attempt, 10.0)
            except OSError:
                failure = ApiError("network-error")
                retry_wait = min(2.0 ** attempt, 10.0)
            if attempt >= self.max_attempts:
                raise failure
            time.sleep(retry_wait if retry_wait is not None else 1.0)


# --------------------------------------------------------------------------
# data files
# --------------------------------------------------------------------------

@dataclass
class Allowlist:
    user: str
    org: str
    merged: list[str]
    flagships: list[str]
    excluded: set[tuple[str, int]] = field(default_factory=set)

    @property
    def merged_ci(self) -> set[str]:
        return {r.lower() for r in self.merged}

    @property
    def flagships_ci(self) -> set[str]:
        return {r.lower() for r in self.flagships}


def read_json_file(path: str, label: str):
    try:
        if os.path.islink(path):
            raise BlockError(f"{label}: symlink refused")
        with open(path, "rb") as fh:
            raw = fh.read(MAX_DATA_BYTES + 1)
        if len(raw) > MAX_DATA_BYTES:
            raise BlockError(f"{label}: file too large")
        return json.loads(raw.decode("utf-8"))
    except BlockError:
        raise
    except (OSError, ValueError):
        raise BlockError(f"{label}: unreadable or not valid JSON") from None


def validate_allowlist(data: object) -> Allowlist:
    if not isinstance(data, dict):
        raise BlockError("allowlist: not an object")
    user, org = data.get("github_user"), data.get("exclude_org")
    for label, value in (("github_user", user), ("exclude_org", org)):
        if not isinstance(value, str) or not NAME_FIELD_RE.fullmatch(value):
            raise BlockError(f"allowlist: bad {label}")
    lists = {}
    for key in ("merged_upstream", "flagships"):
        entries = data.get(key)
        if not isinstance(entries, list) or not entries:
            raise BlockError(f"allowlist: {key} missing or empty")
        for entry in entries:
            if not valid_repo(entry):
                raise BlockError(f"allowlist: invalid entry in {key}")
        lists[key] = list(entries)
    excluded: set[tuple[str, int]] = set()
    raw_excluded = data.get("excluded_prs", [])
    if not isinstance(raw_excluded, list):
        raise BlockError("allowlist: excluded_prs not a list")
    for entry in raw_excluded:
        m = EXCLUDED_PR_RE.fullmatch(entry) if isinstance(entry, str) else None
        if not m or not valid_repo(m.group(1)):
            raise BlockError("allowlist: invalid excluded_prs entry")
        excluded.add((m.group(1).lower(), int(m.group(2))))
    return Allowlist(user, org, lists["merged_upstream"], lists["flagships"], excluded)


def load_allowlist(data_dir: str) -> Allowlist:
    return validate_allowlist(read_json_file(os.path.join(data_dir, "allowlist.json"), "allowlist"))


def load_notes(data_dir: str) -> tuple[dict[str, str], int]:
    """Return (notes keyed by lower-case owner/repo#N, count rejected)."""
    data = read_json_file(os.path.join(data_dir, "pr-notes.json"), "pr-notes")
    if not isinstance(data, dict):
        raise BlockError("pr-notes: not an object")
    notes: dict[str, str] = {}
    rejected = 0
    for key, value in data.items():
        m = NOTE_KEY_RE.fullmatch(key) if isinstance(key, str) else None
        frag = note_fragment(value)
        if not m or not valid_repo(m.group(1)) or frag is None:
            rejected += 1
            continue
        notes[key.lower()] = frag
    return notes, rejected


def load_flagships(data_dir: str, allow: Allowlist) -> list[dict]:
    data = read_json_file(os.path.join(data_dir, "flagships.json"), "flagships")
    entries = data.get("flagships") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise BlockError("flagships: missing or empty list")
    out = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise BlockError("flagships: entry is not an object")
        name, repo, workflow, check = (entry.get(k) for k in ("name", "repo", "workflow", "check"))
        if not valid_repo(repo) or repo.lower() not in allow.flagships_ci:
            raise BlockError("flagships: repo missing from allowlist or invalid")
        if not isinstance(workflow, str) or not WORKFLOW_FILE_RE.fullmatch(workflow):
            raise BlockError("flagships: invalid workflow file name")
        for label, value in (("name", name), ("check", check)):
            if (not isinstance(value, str) or not NAME_RE.fullmatch(value)
                    or value != value.strip() or has_denied(value)):
                raise BlockError(f"flagships: {label} fails the text allowlist")
        out.append({"name": name, "repo": repo, "workflow": workflow, "check": check})
    return out


# --------------------------------------------------------------------------
# merged-upstream block
# --------------------------------------------------------------------------

def search_merged(client: GitHubClient, allow: Allowlist) -> list[dict]:
    query = (f"is:pr is:merged is:public author:{allow.user} -user:{allow.user} "
             f"-org:{allow.org}")
    items: list[dict] = []
    page = 1
    while True:
        data = client.get_json("/search/issues", {
            "q": query, "per_page": SEARCH_PAGE_SIZE, "page": page,
            "sort": "created", "order": "asc"})
        if not isinstance(data, dict):
            raise BlockError("search: unexpected response shape")
        if data.get("incomplete_results") is not False:
            raise BlockError("search: incomplete_results is not false")
        total = data.get("total_count")
        batch = data.get("items")
        if isinstance(total, bool) or not isinstance(total, int) or total < 0 or not isinstance(batch, list):
            raise BlockError("search: unexpected response shape")
        if total >= SEARCH_NEAR_LIMIT:
            raise BlockError("search: total_count is near the 1000-result search cap")
        items.extend(batch)
        if len(batch) < SEARCH_PAGE_SIZE or len(items) >= total:
            break
        page += 1
        if page > SEARCH_MAX_PAGES:
            raise BlockError("search: too many pages")
    if len(items) < total:
        raise BlockError("search: fewer items returned than total_count")
    return items


def repo_from_item(item: dict) -> str | None:
    url = item.get("repository_url")
    prefix = API_ROOT + "/repos/"
    if not isinstance(url, str) or not url.startswith(prefix):
        return None
    repo = url[len(prefix):]
    return repo if valid_repo(repo) else None


def verify_public(client: GitHubClient, repo: str) -> None:
    info = client.get_json(f"/repos/{repo}")
    if not isinstance(info, dict) or info.get("private") is not False:
        raise BlockError("a result repository is not confirmed public")
    full = info.get("full_name")
    if not isinstance(full, str) or full.lower() != repo.lower():
        raise BlockError("a result repository name did not match on re-check")


def existing_block_lines(text: str, name: str) -> list[str]:
    s, e = locate_block(text, name)
    inner = text[s + 1:e - 1] if e - 1 > s + 1 else ""
    return inner.split("\n") if inner else []


def gen_merged(client: GitHubClient, data_dir: str, inject: str, current_text: str,
               allow_shrink: bool = False) -> list[str]:
    allow = load_allowlist_for_merged(data_dir, inject)
    notes, rejected = load_notes(data_dir)
    items = search_merged(client, allow)

    allowed = allow.merged_ci
    rows: dict[tuple[str, int], tuple[str, str, str]] = {}
    not_allowlisted = excluded = skipped = 0
    for item in items:
        if not isinstance(item, dict):
            raise BlockError("search: item is not an object")
        repo_info = item.get("repository")
        if item.get("private") is True or (isinstance(repo_info, dict) and repo_info.get("private") is True):
            raise BlockError("a result is marked private")
        repo = repo_from_item(item)
        number = item.get("number")
        pr = item.get("pull_request")
        user = item.get("user")
        if (repo is None or isinstance(number, bool) or not isinstance(number, int) or number < 1
                or not isinstance(pr, dict)):
            skipped += 1
            continue
        if (repo.lower(), number) in allow.excluded:
            excluded += 1
            continue
        if repo.lower() not in allowed:
            not_allowlisted += 1
            continue
        login = user.get("login") if isinstance(user, dict) else None
        merged_at = pr.get("merged_at")
        if (not isinstance(login, str) or login.lower() != allow.user.lower()
                or not isinstance(merged_at, str) or not merged_at):
            skipped += 1
            continue
        rows[(repo.lower(), number)] = (repo, merged_at, item.get("title"))  # type: ignore[assignment]

    verified: set[str] = set()
    for key in rows:
        if key[0] not in verified:
            verify_public(client, rows[key][0])
            verified.add(key[0])

    ordered = sorted(rows.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    ordered.sort(key=lambda kv: kv[1][1], reverse=True)
    lines = []
    for (low_repo, number), (repo, _merged_at, title) in ordered:
        frag = notes.get(f"{low_repo}#{number}") or title_fragment(title, number)
        lines.append(f"- [{repo} #{number}](https://github.com/{repo}/pull/{number}): {frag}")
    for line in lines:
        if validate_merged_row(line) is None:
            raise BlockError("generated row failed the row grammar")
    if not lines:
        raise BlockError("empty result: no allowlisted merged pull requests found")
    previous = [r for r in (validate_merged_row(x) for x in existing_block_lines(current_text, BLOCK_MERGED)) if r]
    if len(lines) < len(previous) and not allow_shrink:
        raise BlockError(f"shrunken result: {len(lines)} rows against {len(previous)} in the existing block")
    if len(lines) < len(previous):
        print(f"  shrink allowed by --allow-shrink: {len(lines)} rows against {len(previous)}")
    print(f"  merged: {len(items)} search results, {len(lines)} rows "
          f"({not_allowlisted} not allowlisted, {excluded} excluded, {skipped} skipped, "
          f"{rejected} notes rejected)")
    return lines


def load_allowlist_for_merged(data_dir: str, inject: str) -> Allowlist:
    raw = read_json_file(os.path.join(data_dir, "allowlist.json"), "allowlist")
    if inject == "bad-allowlist" and isinstance(raw, dict) and isinstance(raw.get("merged_upstream"), list):
        raw = dict(raw)
        raw["merged_upstream"] = list(raw["merged_upstream"]) + ["not a valid repo!"]
    return validate_allowlist(raw)


# --------------------------------------------------------------------------
# flagships block
# --------------------------------------------------------------------------

def flagship_status(client: GitHubClient, entry: dict) -> str:
    repo = entry["repo"]
    try:
        info = client.get_json(f"/repos/{repo}")
    except ApiError as exc:
        if exc.kind == "not-found":
            return "unavailable"
        raise
    if not isinstance(info, dict):
        raise BlockError("repository response had an unexpected shape")
    if info.get("private") is not False:
        raise BlockError("a flagship repository is not confirmed public")
    full = info.get("full_name")
    if not isinstance(full, str) or full.lower() != repo.lower():
        return "unavailable"          # renamed or moved
    if info.get("archived") is True:
        return "unavailable"
    branch = info.get("default_branch")
    if not isinstance(branch, str) or not BRANCH_RE.fullmatch(branch):
        raise BlockError("repository default branch is invalid")
    try:
        data = client.get_json(
            f"/repos/{repo}/actions/workflows/{entry['workflow']}/runs",
            {"branch": branch, "status": "completed", "per_page": 10})
    except ApiError as exc:
        if exc.kind == "not-found":
            return "unavailable"
        raise
    runs = data.get("workflow_runs") if isinstance(data, dict) else None
    if not isinstance(runs, list):
        raise BlockError("workflow runs response had an unexpected shape")
    for run in runs:
        if not isinstance(run, dict):
            continue
        if run.get("event") in ("pull_request", "pull_request_target"):
            continue
        if run.get("head_branch") not in (None, branch):
            continue
        conclusion = run.get("conclusion")
        if conclusion == "success":
            return "passing"
        if conclusion in ("failure", "timed_out", "startup_failure"):
            return "failing"
    return "unavailable"


def gen_flagships(client: GitHubClient, data_dir: str, inject: str, current_text: str,
                  allow_shrink: bool = False) -> list[str]:
    allow = load_allowlist(data_dir)
    entries = load_flagships(data_dir, allow)
    lines = [FLAG_HEADER, FLAG_SEPARATOR]
    counts = dict.fromkeys(STATUSES, 0)
    for entry in entries:
        status = flagship_status(client, entry)
        counts[status] += 1
        lines.append(f"| [{entry['name']}](https://github.com/{entry['repo']}) | {entry['check']} | {status} |")
    for line in lines[2:]:
        if validate_flagship_row(line) is None:
            raise BlockError("generated row failed the row grammar")
    print(f"  flagships: {len(entries)} rows ({counts['passing']} passing, "
          f"{counts['failing']} failing, {counts['unavailable']} unavailable)")
    return lines


# --------------------------------------------------------------------------
# marker splice
# --------------------------------------------------------------------------

def locate_block(text: str, name: str) -> tuple[int, int]:
    """Return (index of the newline ending the START line, index of END marker)."""
    start, end = marker_start(name), marker_end(name)
    if text.count(start) != 1 or text.count(end) != 1:
        raise BlockError(f"{name}: need exactly one START and one END marker")
    s, e = text.find(start), text.find(end)
    after = s + len(start)
    if e < after + 1:
        raise BlockError(f"{name}: END marker is not after the START line")
    if (s > 0 and text[s - 1] != "\n") or text[after] != "\n":
        raise BlockError(f"{name}: START marker must be alone on its line")
    tail = e + len(end)
    if text[e - 1] != "\n" or (tail < len(text) and text[tail] != "\n"):
        raise BlockError(f"{name}: END marker must be alone on its line")
    return after, e


def check_structure(text: str) -> None:
    spans = []
    for name in BLOCK_NAMES:
        s, e = locate_block(text, name)
        spans.append((s, e))
    spans.sort()
    for (_, e1), (s2, _) in zip(spans, spans[1:]):
        if e1 > s2:
            raise BlockError("blocks overlap or nest")


def splice(text: str, name: str, lines: list[str]) -> str:
    after, e = locate_block(text, name)
    return text[:after] + "\n" + "\n".join(lines) + "\n" + text[e:]


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def read_readme(path: str) -> str:
    if os.path.islink(path):
        raise FatalError("README path is a symlink")
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_README_BYTES + 1)
    except OSError:
        raise FatalError("README could not be read") from None
    if len(raw) > MAX_README_BYTES:
        raise FatalError("README is too large")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise FatalError("README is not valid UTF-8") from None
    if "\r" in text:
        raise FatalError("README has CR characters; LF line endings are required")
    return text


def write_out(path: str, text: str) -> None:
    if os.path.islink(path):
        raise FatalError("output path is a symlink")
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    tmp = os.path.join(parent, f".{os.path.basename(path)}.tmp{os.getpid()}")
    try:
        with open(tmp, "wb") as fh:
            fh.write(text.encode("utf-8"))
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise FatalError("output could not be written") from None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Regenerate the generated README blocks.")
    p.add_argument("--readme", required=True, help="README with the block markers")
    p.add_argument("--out", help="output path (default: same as --readme, i.e. in place)")
    p.add_argument("--data-dir", default="data", help="directory with allowlist/flagships/pr-notes JSON")
    p.add_argument("--dry-run", action="store_true",
                   help="never write the --readme path; still writes a different --out")
    p.add_argument("--inject-fault", default="none", choices=FAULTS,
                   help="deterministic failure for testing (see module docstring)")
    p.add_argument("--allow-shrink", action="store_true",
                   help="maintainer only: let the merged block end with fewer rows than the README "
                        "holds, to remove a row on purpose; scheduled workflows never pass this")
    p.add_argument("--allow-non-ghs", action="store_true",
                   help="local development only: accept a token that does not start with ghs_")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except FatalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def run(args: argparse.Namespace) -> int:
    if args.inject_fault not in FAULTS:
        raise FatalError("unknown --inject-fault value")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise FatalError("GITHUB_TOKEN is not set")
    if not token.startswith("ghs_") and not args.allow_non_ghs:
        raise FatalError("GITHUB_TOKEN is not a ghs_ installation token (use --allow-non-ghs for local runs)")

    out_path = args.out or args.readme
    in_place = os.path.abspath(out_path) == os.path.abspath(args.readme)
    base_text = read_readme(args.readme)
    try:
        check_structure(base_text)
    except BlockError as exc:
        raise FatalError(f"README markers: {exc}") from None

    client = GitHubClient(token)
    generators = ((BLOCK_MERGED, gen_merged), (BLOCK_FLAGSHIPS, gen_flagships))
    text = base_text
    failed: list[str] = []
    for name, gen in generators:
        print(f"{name}:")
        try:
            lines = gen(client, args.data_dir, args.inject_fault, text,
                        allow_shrink=getattr(args, "allow_shrink", False))
            target = text
            if args.inject_fault == "bad-marker" and name == BLOCK_FLAGSHIPS:
                target = text + "\n" + marker_start(name) + "\n"
            text = splice(target, name, lines)  # raises on a corrupted copy (fault injection)
            print(f"  ok ({len(lines)} lines)")
        except BlockError as exc:
            failed.append(name)
            print(f"  FAILED: {exc}")
        except Exception as exc:  # defensive: never leak message text
            failed.append(name)
            print(f"  FAILED: unexpected {type(exc).__name__}")
    print(f"api calls: {client.calls}")

    if in_place and args.dry_run:
        print("dry run: README not written")
    elif text != base_text or not in_place:
        write_out(out_path, text)
        print("wrote output" if text != base_text else "wrote output (no change)")
    else:
        print("no change")
    if failed:
        print(f"result: FAILED blocks: {', '.join(failed)}")
        return 1
    print("result: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
