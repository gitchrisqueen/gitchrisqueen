#!/usr/bin/env python3
"""Publish guard for the generated profile README.

Compares the README as it was before a generator run (--base) with the one the
run produced (--new) and exits non-zero unless every rule holds:

  1. each file is a regular file (no symlinks);
  2. exactly one START and one END marker line per block, in order, in both files;
  3. the two files differ only on lines between the markers;
  4. every line between the markers matches the exact row grammar (no raw HTML,
     no images) and is not shorter than the base block (a block may not empty);
     the merged block may not lose rows unless --allow-shrink is given;
  5. every URL is https://github.com/...;
  6. every row's owner/repo is in the allowlist for that block;
  7. with --root or --git-diff, no symlink exists anywhere in the tree;
  8. with --git-diff, `git diff --name-only` (working tree and index) lists only
     README.md.

Messages carry rule names and line numbers only, never file content. Standard
library only. Exit codes: 0 pass, 1 any violation (unreadable input included),
2 command-line usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

# --- grammar (kept identical to update_profile.py; a test enforces parity)
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
DENIED_SUBSTRINGS = ("://", "www.", "<!--", "-->", "](", "<", ">")
URL_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S*")

BLOCK_MERGED = "MERGED-UPSTREAM"
BLOCK_FLAGSHIPS = "FLAGSHIPS"
BLOCK_NAMES = (BLOCK_MERGED, BLOCK_FLAGSHIPS)
MAX_FILE_BYTES = 2_000_000


def marker_start(name: str) -> str:
    return f"<!-- {name}:START -->"


def marker_end(name: str) -> str:
    return f"<!-- {name}:END -->"


def valid_repo(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 140 or not REPO_RE.fullmatch(value):
        return False
    return all(part.strip(".") for part in value.split("/"))


def has_denied(text: str) -> bool:
    low = text.lower()
    return any(item in low for item in DENIED_SUBSTRINGS)


def merged_row(line: str) -> str | None:
    """Return the row's owner/repo if the line fits the merged-row grammar."""
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
    return repo if ok else None


def flagship_row(line: str) -> str | None:
    m = FLAG_ROW_RE.fullmatch(line)
    if not m or not valid_repo(m.group("repo")):
        return None
    for key in ("name", "check"):
        value = m.group(key)
        if value != value.strip() or has_denied(value):
            return None
    return m.group("repo")


def read_text(path: str, problems: list[str], label: str) -> str | None:
    if os.path.islink(path):
        problems.append(f"{label}: is a symlink")
        return None
    if not os.path.isfile(path):
        problems.append(f"{label}: not a regular file")
        return None
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            problems.append(f"{label}: too large")
            return None
        return raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        problems.append(f"{label}: unreadable or not UTF-8")
        return None


def load_allowlist(path: str, problems: list[str]) -> dict[str, set[str]] | None:
    text = read_text(path, problems, "allowlist")
    if text is None:
        return None
    try:
        data = json.loads(text)
        out = {}
        for key, block in (("merged_upstream", BLOCK_MERGED), ("flagships", BLOCK_FLAGSHIPS)):
            entries = data[key]
            if not isinstance(entries, list) or not entries or not all(valid_repo(e) for e in entries):
                raise ValueError
            out[block] = {e.lower() for e in entries}
        return out
    except (ValueError, KeyError, TypeError):
        problems.append("allowlist: malformed (needs non-empty merged_upstream and flagships repo lists)")
        return None


def split_blocks(lines: list[str], label: str, problems: list[str]):
    """Return (outside_lines_with_placeholders, {block: (first_line_no, inner_lines)}) or None."""
    positions = {}
    for name in BLOCK_NAMES:
        starts = [i for i, ln in enumerate(lines) if ln == marker_start(name)]
        ends = [i for i, ln in enumerate(lines) if ln == marker_end(name)]
        text_hits = sum(ln.count(marker_start(name)) + ln.count(marker_end(name)) for ln in lines)
        if len(starts) != 1 or len(ends) != 1 or text_hits != 2:
            problems.append(f"{label}: {name} needs exactly one START and one END marker, each alone on its line")
            return None
        if ends[0] < starts[0]:
            problems.append(f"{label}: {name} END comes before START")
            return None
        positions[name] = (starts[0], ends[0])
    ordered = sorted(positions.items(), key=lambda kv: kv[1][0])
    for (_, (_, e1)), (_, (s2, _)) in zip(ordered, ordered[1:]):
        if e1 > s2:
            problems.append(f"{label}: blocks overlap or nest")
            return None
    outside: list[str] = []
    inner: dict[str, tuple[int, list[str]]] = {}
    cursor = 0
    for name, (s, e) in ordered:
        outside.extend(lines[cursor:s + 1])
        outside.append(f"\0BLOCK {name}")
        inner[name] = (s + 2, lines[s + 1:e])
        cursor = e
    outside.extend(lines[cursor:])
    return outside, inner


def check_block_lines(name: str, first_line_no: int, lines: list[str], allowed: set[str],
                      problems: list[str]) -> int:
    """Check one block's lines against the grammar; return the count of data rows."""
    rows = 0
    if name == BLOCK_FLAGSHIPS:
        body = lines
        if body:
            if body[0] != FLAG_HEADER or len(body) < 2 or body[1] != FLAG_SEPARATOR:
                problems.append(f"{name}: table must start with the exact header and separator rows")
            start_idx = 2
        else:
            start_idx = 0
        for idx in range(start_idx, len(body)):
            ln_no = first_line_no + idx
            repo = flagship_row(body[idx])
            if repo is None:
                problems.append(f"{name}: line {ln_no} does not match the flagship row grammar")
                continue
            rows += 1
            if repo.lower() not in allowed:
                problems.append(f"{name}: line {ln_no} repo is not in the allowlist")
            if body[idx].count("|") != 4:
                problems.append(f"{name}: line {ln_no} has the wrong column count")
    else:
        for idx, line in enumerate(lines):
            ln_no = first_line_no + idx
            repo = merged_row(line)
            if repo is None:
                problems.append(f"{name}: line {ln_no} does not match the merged row grammar")
                continue
            rows += 1
            if repo.lower() not in allowed:
                problems.append(f"{name}: line {ln_no} repo is not in the allowlist")
    # URL rule, defence in depth: anything with a scheme must be github.com.
    for idx, line in enumerate(lines):
        for url in URL_RE.findall(line):
            if not re.fullmatch(rf"https://github\.com/{REPO_PART}/{REPO_PART}(/pull/[0-9]+)?\)?:?", url):
                problems.append(f"{name}: line {first_line_no + idx} has a URL that is not on github.com")
        if re.search(r"www\.", line, re.IGNORECASE):
            problems.append(f"{name}: line {first_line_no + idx} has a www. host")
    return rows


def find_symlinks(root: str) -> list[str]:
    hits = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for entry in dirnames + filenames:
            full = os.path.join(dirpath, entry)
            if os.path.islink(full):
                hits.append(os.path.relpath(full, root))
    return hits


def git_changed_files(root: str) -> list[str] | None:
    """Names from `git diff --name-only` (working tree and index). Read-only."""
    names: set[str] = set()
    for extra in ([], ["--cached"]):
        cmd = ["git", "-C", root, "diff", "--name-only", "-z", *extra]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=60, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        names.update(p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p)
    return sorted(names)


def check(base_path: str, new_path: str, allowlist_path: str, *, root: str | None = None,
          git_diff: bool = False, allow_shrink: bool = False) -> list[str]:
    problems: list[str] = []
    base = read_text(base_path, problems, "base")
    new = read_text(new_path, problems, "new")
    allow = load_allowlist(allowlist_path, problems)
    if root is not None or git_diff:
        tree = root if root is not None else "."
        for rel in find_symlinks(tree):
            problems.append(f"tree: symlink present at {rel}")
    if base is None or new is None:
        return problems
    split_base = split_blocks(base.split("\n"), "base", problems)
    split_new = split_blocks(new.split("\n"), "new", problems)
    if split_base is not None and split_new is not None:
        out_base, in_base = split_base
        out_new, in_new = split_new
        if out_base != out_new:
            problems.append("diff: lines outside the generated blocks changed")
        for name in BLOCK_NAMES:
            first_no, lines = in_new[name]
            rows = check_block_lines(name, first_no, lines, allow[name] if allow else set(), problems)
            base_lines = in_base[name][1]
            if base_lines and not lines:
                problems.append(f"{name}: block became empty")
            if name == BLOCK_MERGED:
                base_rows = sum(1 for ln in base_lines if merged_row(ln) is not None)
                if rows < base_rows and not allow_shrink:
                    problems.append(f"{name}: block has fewer rows than the base ({rows} < {base_rows})")
    if git_diff:
        changed = git_changed_files(root if root is not None else ".")
        if changed is None:
            problems.append("git: could not run git diff")
        elif any(name != "README.md" for name in changed):
            problems.append("git: files other than README.md changed")
    return problems


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Guard a regenerated profile README before it is published.")
    p.add_argument("--base", required=True, help="README before the generator ran")
    p.add_argument("--new", required=True, help="README after the generator ran")
    p.add_argument("--allowlist", required=True, help="data/allowlist.json")
    p.add_argument("--root", help="directory to scan for symlinks")
    p.add_argument("--git-diff", action="store_true",
                   help="also require `git diff --name-only` to list only README.md")
    p.add_argument("--allow-shrink", action="store_true",
                   help="maintainer only: accept a merged block with fewer rows than the base, to "
                        "remove a row on purpose; scheduled workflows never pass this")
    args = p.parse_args(argv)
    problems = check(args.base, args.new, args.allowlist, root=args.root, git_diff=args.git_diff,
                     allow_shrink=args.allow_shrink)
    for line in problems:
        print(f"guard: {line}", file=sys.stderr)
    if problems:
        print(f"guard: FAILED ({len(problems)} problem(s))", file=sys.stderr)
        return 1
    print("guard: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
