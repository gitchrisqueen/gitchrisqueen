#!/usr/bin/env python3
"""Prepare contribution-snake SVGs for the profile page.

The snake generator (Platane/snk, svg-only mode) has no still-image option, so
this script derives one from its animated output:

    make_snake_static.py IN.svg OUT.svg --bg "#ffffff"

Static twin (default):
  * removes every ``@keyframes`` rule and every ``animation*`` declaration, and
    nothing else, so every fill and stroke rule survives and the page shows the
    whole contribution calendar with the snake parked at its start;
  * injects an opaque background rectangle as the first child of the root
    element, so contrast never depends on the page theme;
  * refuses to write the file if the result still animates, or if the cell and
    snake fills did not survive (for example when a style block was stripped).

Animated copy (``--keep-animation``):
  * keeps the animation, injects the same opaque background rectangle, and adds
    the ``prefers-reduced-motion`` rule that stops the animation.

Both modes then run scripts/lint_svg.py on the result unless ``--no-lint`` is
given. The output file is written only after every check passes.

Only the standard library is used. Input is treated as untrusted: DOCTYPE and
ENTITY declarations are rejected before any XML parsing.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_INPUT_BYTES = 5_000_000
DEFAULT_MIN_CELLS = 100
BG_ID = "snake-bg"
MOTION_RULE = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"
SMIL_ELEMENTS = {"animate", "animatetransform", "animatemotion", "set"}

_STYLE_RE = re.compile(r"(<style\b[^>]*>)(.*?)(</style\s*>)", re.DOTALL | re.IGNORECASE)
_SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>", re.DOTALL | re.IGNORECASE)
_BG_RE = re.compile(r'<rect\b[^>]*\bid="' + BG_ID + r'"[^>]*/>', re.IGNORECASE)
_ANIM_PROP_RE = re.compile(r"^(?:-[a-z]+-)?animation(?:-[a-z-]+)?$")
_KEYFRAMES_RE = re.compile(r"^@(?:-[a-z]+-)?keyframes\b", re.IGNORECASE)
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class StaticTwinError(ValueError):
    """The SVG cannot be turned into a safe, complete output."""


# ---------------------------------------------------------------- CSS helpers


def _skip_string(text: str, i: int) -> int:
    """Return the index just after the quoted string that starts at ``i``."""
    quote = text[i]
    j = i + 1
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == quote:
            return j + 1
        j += 1
    return len(text)


def _parse_blocks(css: str) -> list[tuple[str, str | None]]:
    """Split CSS into top-level (prelude, body) pairs. body is None for ``x;``."""
    items: list[tuple[str, str | None]] = []
    i, n = 0, len(css)
    while i < n:
        j = i
        while j < n and css[j] not in "{;":
            j = _skip_string(css, j) if css[j] in "\"'" else j + 1
        if j >= n:
            tail = css[i:].strip()
            if tail:
                items.append((tail, None))
            break
        if css[j] == ";":
            items.append((css[i : j + 1].strip(), None))
            i = j + 1
            continue
        depth, k = 1, j + 1
        while k < n and depth:
            c = css[k]
            if c in "\"'":
                k = _skip_string(css, k)
                continue
            depth += (c == "{") - (c == "}")
            k += 1
        if depth:
            raise StaticTwinError("unbalanced braces in <style>")
        items.append((css[i:j].strip(), css[j + 1 : k - 1]))
        i = k
    return items


def _declarations(body: str) -> list[str]:
    """Split a rule body on top-level semicolons (not inside parens or strings)."""
    parts: list[str] = []
    cur: list[str] = []
    depth, i = 0, 0
    while i < len(body):
        c = body[i]
        if c in "\"'":
            j = _skip_string(body, i)
            cur.append(body[i:j])
            i = j
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth = max(0, depth - 1)
        if c == ";" and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _prop(decl: str) -> str:
    return decl.split(":", 1)[0].strip().lower()


def _value(decl: str) -> str:
    return decl.split(":", 1)[1].strip() if ":" in decl else ""


def _is_animation_decl(decl: str) -> bool:
    return bool(_ANIM_PROP_RE.match(_prop(decl)))


def strip_css_animation(css: str) -> str:
    """Drop @keyframes rules and animation* declarations; keep everything else."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    out: list[str] = []
    for prelude, body in _parse_blocks(css):
        if body is None:
            out.append(prelude)
            continue
        if _KEYFRAMES_RE.match(prelude):
            continue
        if prelude.startswith("@"):
            inner = strip_css_animation(body)
            if inner:
                out.append(f"{prelude}{{{inner}}}")
            continue
        kept = [d for d in _declarations(body) if not _is_animation_decl(d)]
        if kept:
            out.append(f"{prelude}{{{';'.join(kept)}}}")
    return "".join(out)


def _flat_rules(css: str) -> list[tuple[str, list[str]]]:
    """Flatten style rules (descending into @media/@supports, skipping keyframes)."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    rules: list[tuple[str, list[str]]] = []
    for prelude, body in _parse_blocks(css):
        if body is None or _KEYFRAMES_RE.match(prelude):
            continue
        if prelude.startswith("@"):
            rules.extend(_flat_rules(body))
        else:
            rules.append((prelude, _declarations(body)))
    return rules


# ---------------------------------------------------------------- SVG helpers


def _reject_unsafe_xml(svg: str) -> None:
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", svg, re.IGNORECASE):
        raise StaticTwinError("DOCTYPE and ENTITY declarations are not allowed")


def _parse_root(svg: str) -> ET.Element:
    _reject_unsafe_xml(svg)
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise StaticTwinError(f"not well-formed XML: {exc}") from exc
    if root.tag.split("}")[-1].lower() != "svg":
        raise StaticTwinError("root element is not <svg>")
    return root


def _attr(tag: str, name: str) -> str | None:
    m = re.search(r"\b" + name + r"""\s*=\s*(?:"([^"]*)"|'([^']*)')""", tag)
    return (m.group(1) if m.group(1) is not None else m.group(2)) if m else None


def _num(value: float) -> str:
    return ("%.4f" % value).rstrip("0").rstrip(".") or "0"


def _geometry(tag: str) -> tuple[float, float, float, float]:
    """Return x, y, width, height of the drawing area from viewBox or width/height."""
    vb = _attr(tag, "viewBox")
    try:
        if vb:
            nums = [float(p) for p in re.split(r"[\s,]+", vb.strip())]
            if len(nums) == 4 and nums[2] > 0 and nums[3] > 0:
                return nums[0], nums[1], nums[2], nums[3]
        else:
            w, h = _attr(tag, "width"), _attr(tag, "height")
            if w and h:
                width = float(re.sub(r"px$", "", w.strip()))
                height = float(re.sub(r"px$", "", h.strip()))
                if width > 0 and height > 0:
                    return 0.0, 0.0, width, height
    except ValueError:
        pass
    raise StaticTwinError("cannot work out the SVG size from viewBox or width/height")


def _normalise_hex(color: str) -> str:
    if not _HEX_RE.match(color):
        raise StaticTwinError(f"--bg must be a hex colour like #ffffff, got {color!r}")
    color = color.lower()
    if len(color) == 4:
        color = "#" + "".join(ch * 2 for ch in color[1:])
    return color


def inject_background(svg: str, bg: str) -> str:
    """Insert an opaque full-size rect as the first child of the root element."""
    bg = _normalise_hex(bg)
    svg = _BG_RE.sub("", svg)
    m = _SVG_OPEN_RE.search(svg)
    if not m or m.group(0).endswith("/>"):
        raise StaticTwinError("no <svg> element with content found")
    x, y, w, h = _geometry(m.group(0))
    rect = (
        f'<rect id="{BG_ID}" x="{_num(x)}" y="{_num(y)}" '
        f'width="{_num(w)}" height="{_num(h)}" fill="{bg}"/>'
    )
    return svg[: m.end()] + rect + svg[m.end() :]


def _map_styles(svg: str, fn) -> str:
    """Apply ``fn`` to the CSS text of every <style> block (CDATA preserved)."""

    def repl(m: re.Match[str]) -> str:
        open_tag, inner, close_tag = m.groups()
        stripped = inner.strip()
        if stripped.startswith("<![CDATA[") and stripped.endswith("]]>"):
            return f"{open_tag}<![CDATA[{fn(stripped[9:-3])}]]>{close_tag}"
        return f"{open_tag}{fn(inner)}{close_tag}"

    return _STYLE_RE.sub(repl, svg)


def add_reduced_motion_rule(svg: str) -> str:
    """Append the reduced-motion rule to the last <style> block (once)."""
    matches = list(_STYLE_RE.finditer(svg))
    if not matches:
        raise StaticTwinError("no <style> block to attach the reduced-motion rule to")
    if re.search(r"prefers-reduced-motion\s*:\s*reduce", svg, re.IGNORECASE):
        return svg
    last = matches[-1]
    open_tag, inner, close_tag = last.groups()
    stripped = inner.strip()
    if stripped.startswith("<![CDATA[") and stripped.endswith("]]>"):
        new_inner = f"<![CDATA[{stripped[9:-3]}{MOTION_RULE}]]>"
    else:
        new_inner = inner + MOTION_RULE
    return svg[: last.start()] + open_tag + new_inner + close_tag + svg[last.end() :]


def make_static(svg: str, bg: str) -> str:
    """Return the static twin of an animated snake SVG."""
    _parse_root(svg)
    if not _STYLE_RE.search(svg):
        raise StaticTwinError("input has no <style> block; refusing to guess")
    return inject_background(_map_styles(svg, strip_css_animation), bg)


def make_animated(svg: str, bg: str) -> str:
    """Return the animated SVG with an opaque background and the motion rule."""
    _parse_root(svg)
    return add_reduced_motion_rule(inject_background(svg, bg))


# ----------------------------------------------------------------- validation


def _style_text(root: ET.Element) -> str:
    return "\n".join(
        (el.text or "") for el in root.iter() if el.tag.split("}")[-1].lower() == "style"
    )


def _count_cells(root: ET.Element) -> int:
    n = 0
    for el in root.iter():
        if el.tag.split("}")[-1].lower() == "rect" and "c" in (el.get("class") or "").split():
            n += 1
    return n


def problems_common(svg: str, min_cells: int) -> list[str]:
    root = _parse_root(svg)
    problems: list[str] = []
    first = next(iter(root), None)
    if first is None or first.tag.split("}")[-1].lower() != "rect" or first.get("id") != BG_ID:
        problems.append("first child is not the injected opaque background rect")
    elif not re.match(r"^#[0-9a-f]{6}$", first.get("fill") or ""):
        problems.append("background rect has no opaque hex fill")
    cells = _count_cells(root)
    if cells < min_cells:
        problems.append(f"only {cells} calendar cells found, expected at least {min_cells}")
    return problems


def static_problems(svg: str, min_cells: int = DEFAULT_MIN_CELLS) -> list[str]:
    """Return a list of reasons the static twin is not acceptable (empty = fine)."""
    problems = problems_common(svg, min_cells)
    root = _parse_root(svg)
    css = _style_text(root)
    if not css.strip():
        problems.append("no style rules left: cell and snake colours were lost")
    if re.search(r"@(?:-[a-z]+-)?keyframes", css, re.IGNORECASE):
        problems.append("@keyframes still present")
    rules = _flat_rules(css)
    if any(_is_animation_decl(d) for _, decls in rules for d in decls):
        problems.append("animation declaration still present")
    for el in root.iter():
        if el.tag.split("}")[-1].lower() in SMIL_ELEMENTS:
            problems.append("SMIL animation element still present")
            break
    base_fills: set[str] = set()
    cell_fills: set[str] = set()
    snake_fills: set[str] = set()
    for selector, decls in rules:
        fills = [_value(d) for d in decls if _prop(d) == "fill"]
        for sel in (s.strip() for s in selector.split(",")):
            if sel == ".c":
                base_fills.update(fills)
            elif re.match(r"^\.c\.", sel):
                cell_fills.update(fills)
            elif re.match(r"^\.s(\.|$)", sel):
                snake_fills.update(fills)
    if not (cell_fills - base_fills):
        problems.append("no non-default calendar cell fill survived")
    if not snake_fills:
        problems.append("no snake fill survived")
    return problems


def animated_problems(svg: str, min_cells: int = DEFAULT_MIN_CELLS) -> list[str]:
    problems = problems_common(svg, min_cells)
    if not re.search(r"prefers-reduced-motion\s*:\s*reduce", svg, re.IGNORECASE):
        problems.append("reduced-motion rule missing")
    return problems


# ------------------------------------------------------------------------ CLI


def _default_lint_script() -> Path:
    return Path(__file__).resolve().with_name("lint_svg.py")


def run_lint(path: Path, lint_script: Path) -> None:
    if not lint_script.is_file():
        raise StaticTwinError(f"lint script not found: {lint_script} (use --no-lint to skip)")
    result = subprocess.run(
        [
            sys.executable,
            str(lint_script),
            "--profile",
            "chart",
            "--require-opaque-background",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()[:2000]
        raise StaticTwinError(f"lint failed for {path.name}: {detail}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Make a static twin (or opaque copy) of a snk SVG.")
    p.add_argument("input", type=Path, help="animated SVG written by the snake generator")
    p.add_argument("output", type=Path, help="where to write the result")
    p.add_argument("--bg", required=True, help="opaque background colour, hex (#rgb or #rrggbb)")
    p.add_argument(
        "--keep-animation",
        action="store_true",
        help="keep the animation; add the background and the reduced-motion rule only",
    )
    p.add_argument("--min-cells", type=int, default=DEFAULT_MIN_CELLS, help="expected cell count")
    p.add_argument("--no-lint", action="store_true", help="skip scripts/lint_svg.py")
    p.add_argument("--lint-script", type=Path, default=None, help="path to lint_svg.py")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    src, dst = args.input, args.output
    try:
        if src.is_symlink():
            raise StaticTwinError("input is a symlink")
        if not src.is_file():
            raise StaticTwinError(f"input not found: {src}")
        if dst.exists() and src.resolve() == dst.resolve():
            raise StaticTwinError("input and output must be different files")
        if src.stat().st_size > MAX_INPUT_BYTES:
            raise StaticTwinError("input is larger than the 5 MB limit")
        svg = src.read_text(encoding="utf-8")
        if args.keep_animation:
            out = make_animated(svg, args.bg)
            problems = animated_problems(out, args.min_cells)
        else:
            out = make_static(svg, args.bg)
            problems = static_problems(out, args.min_cells)
        if problems:
            raise StaticTwinError("; ".join(problems))
        dst.parent.mkdir(parents=True, exist_ok=True)
        partial = dst.with_name(dst.stem + ".partial.svg")
        partial.write_text(out, encoding="utf-8", newline="")
        try:
            if not args.no_lint:
                run_lint(partial, args.lint_script or _default_lint_script())
            os.replace(partial, dst)
        finally:
            if partial.exists():
                partial.unlink()
    except (StaticTwinError, OSError, UnicodeDecodeError, subprocess.SubprocessError) as exc:
        print(f"make_snake_static: {exc}", file=sys.stderr)
        return 1
    mode = "animated" if args.keep_animation else "static"
    print(f"make_snake_static: wrote {mode} {dst} ({dst.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
