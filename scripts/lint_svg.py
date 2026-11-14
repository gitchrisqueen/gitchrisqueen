#!/usr/bin/env python3
"""Lint the profile's SVG assets for safety, motion limits and size.

Usage:
    python scripts/lint_svg.py FILE... [--require-opaque-background]
        [--profile banner|chart] [--min-bytes N] [--max-bytes N]
        [--expect TAG[=N]]...

Exit status: 0 when every file passes, 1 when any file has a violation,
2 on a usage error.

Every file is parsed as XML (never grepped alone). Element and attribute
names are compared case-insensitively, and attribute values are checked after
the XML parser has decoded character references, so `<SCRIPT>` and
`&#x6A;avascript:` are caught the same way as their plain forms. A DOCTYPE or
ENTITY declaration is rejected before parsing.

Checks for every profile:
  * rejected elements: script, foreignObject, animate, animateTransform,
    animateMotion, set (and other active-content elements such as iframe);
  * rejected attributes: any `on*` event handler; any `href` / `xlink:href`
    that is not a `#fragment`; any `url()` that is not `url(#fragment)`;
    `javascript:` anywhere; inline `animation` in a style attribute;
  * rejected CSS: `@import`, non-fragment `url()`, `expression(`; and, in
    style-element text, style attributes and every other attribute value
    (after comment stripping and HTML-unescaping, case-insensitive): any
    backslash (CSS escapes can spell `url(`), `://`, `image-set(`, `image(`,
    `src(`, `cross-fade(` and `@font-face`;
  * no processing instruction other than a leading `<?xml ...?>` declaration
    (a `<?xml-stylesheet ...?>` can pull in an external stylesheet);
  * the root element is `svg` with a numeric four-part viewBox;
  * the file is at least `--min-bytes` bytes (and at most `--max-bytes` when
    given) and contains each `--expect`ed element at least N times;
  * an animated file (one with `@keyframes` or an `animation` declaration)
    must contain `@media (prefers-reduced-motion: reduce){*{animation:none!important}}`;
  * a file whose name ends in `-static.svg` must contain no animation.

The `banner` profile (the default; header and footer) also enforces:
  * viewBox width <= 600 and height >= 140;
  * at least one `text` element;
  * motion limits, read from the stylesheet's keyframes:
      - at most one animation in the file (one infinite loop);
      - duration (one keyframe pass) >= 12 s;
      - keyframes may change only `transform`, and only with
        translate/translateX/translateY in px; no opacity, colour or
        visibility change, so nothing can flash;
      - amplitude <= 8 px AND <= 6% of the viewBox height (stricter wins).
        Amplitude is the largest vertical translation in the keyframes plus,
        when the layer also moves sideways (a drifting wave), half the
        vertical extent of each path on the moving layer, measured by
        sampling the path geometry (centre line; stroke width not counted);
      - no `text` on a moving layer, and a moving layer holds only `g` and
        `path` elements with no `transform` attribute.

The `chart` profile (the contribution snake) runs only the common checks;
its motion is a chart sweep, not a wave, and its static twin carries none.

`--require-opaque-background` requires the first drawable child of the root
(after title, desc, metadata, style and defs) to be a `rect` that covers the
whole viewBox with an opaque solid fill.

The module is importable: `lint_text(text, name, ...)` and `lint_file(path,
...)` return a `LintResult` with `violations` and `metrics`.
"""

from __future__ import annotations

import argparse
import html
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

MAX_BANNER_WIDTH = 600.0
MIN_BANNER_HEIGHT = 140.0
MAX_AMPLITUDE_PX = 8.0
MAX_AMPLITUDE_FRACTION = 0.06
MIN_PERIOD_S = 12.0
MAX_ANIMATIONS = 1
DEFAULT_MIN_BYTES = 400

# Substrings refused in any CSS text or attribute value, checked after comment
# stripping, HTML-unescaping and whitespace removal, case-insensitively.
CSS_FORBIDDEN_SUBSTRINGS = (
    "://",
    "image-set(",
    "image(",
    "src(",
    "cross-fade(",
    "@font-face",
)
# Any processing instruction other than the XML declaration at the very start.
PROCESSING_INSTRUCTION_RE = re.compile(r"<\?(?!xml[\s?])", re.I)

FORBIDDEN_ELEMENTS = {
    "script",
    "foreignobject",
    "animate",
    "animatetransform",
    "animatemotion",
    "animatecolor",
    "set",
    "discard",
    "handler",
    "listener",
    "iframe",
    "embed",
    "object",
    "audio",
    "video",
}
NON_DRAWING = {"title", "desc", "metadata", "style", "defs"}
MOVING_LAYER_ALLOWED = {"g", "path", "title", "desc"}
TEXT_ELEMENTS = {"text", "tspan", "textpath"}

ANIMATION_KEYWORDS = {
    "linear", "ease", "ease-in", "ease-out", "ease-in-out", "step-start",
    "step-end", "normal", "reverse", "alternate", "alternate-reverse", "none",
    "forwards", "backwards", "both", "running", "paused", "infinite",
}
REDUCED_MOTION_MEDIA = re.compile(
    r"^@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)$", re.I
)
URL_FRAGMENT_ONLY = re.compile(r"url\(\s*['\"]?\s*#", re.I)
TIME_RE = re.compile(r"^(-?\d*\.?\d+)(ms|s)$", re.I)
NUMBER_RE = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
PATH_TOKEN_RE = re.compile(
    r"([MmLlHhVvCcSsQqTtAaZz])|(-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)"
)


@dataclass
class LintResult:
    name: str
    violations: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def add(self, rule: str, message: str) -> None:
        entry = f"{rule}: {message}"
        if entry not in self.violations:
            self.violations.append(entry)

    @property
    def ok(self) -> bool:
        return not self.violations


# --------------------------------------------------------------------------
# small helpers


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def parse_blocks(css: str) -> list[tuple[str, str]]:
    """Split CSS into top-level (prelude, body) pairs with balanced braces."""
    blocks: list[tuple[str, str]] = []
    i, n, start = 0, len(css), 0
    while i < n:
        ch = css[i]
        if ch == "{":
            prelude = css[start:i].strip()
            depth, j = 1, i + 1
            while j < n and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            if depth:
                raise ValueError("unbalanced braces in stylesheet")
            blocks.append((prelude, css[i + 1 : j - 1]))
            i = start = j
            continue
        if ch == "}":
            raise ValueError("unbalanced braces in stylesheet")
        if ch == ";":  # bare statement such as @charset or @import
            stmt = css[start:i].strip()
            if stmt:
                blocks.append((stmt, ""))
            start = i + 1
        i += 1
    tail = css[start:].strip()
    if tail:
        blocks.append((tail, ""))
    return blocks


def parse_decls(body: str) -> list[tuple[str, str]]:
    decls = []
    for part in body.split(";"):
        if ":" not in part:
            continue
        prop, value = part.split(":", 1)
        decls.append((prop.strip().lower(), value.strip()))
    return decls


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def normalize_css(value: str) -> str:
    """HTML-unescape (until stable), then strip CSS comments."""
    for _ in range(4):
        decoded = html.unescape(value)
        if decoded == value:
            break
        value = decoded
    return strip_css_comments(value)


# --------------------------------------------------------------------------
# path geometry


def path_points(d: str) -> list[tuple[float, float]]:
    """Return sampled points along a path. Raises ValueError on arcs/garbage."""
    tokens = PATH_TOKEN_RE.findall(d)
    if re.sub(r"[\s,]", "", d) != "".join(c or num for c, num in tokens):
        raise ValueError("unparseable path data")
    pts: list[tuple[float, float]] = []
    cmd = ""
    nums: list[float] = []
    seq: list[tuple[str, list[float]]] = []
    for c, num in tokens:
        if c:
            if cmd:
                seq.append((cmd, nums))
            cmd, nums = c, []
        else:
            nums.append(float(num))
    if cmd:
        seq.append((cmd, nums))

    x = y = sx = sy = 0.0
    last_ctrl: tuple[float, float] | None = None
    last_q: tuple[float, float] | None = None
    arity = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "t": 2, "z": 0}

    def cubic(p0, p1, p2, p3):
        for k in range(1, 33):
            t = k / 32
            mt = 1 - t
            pts.append((
                mt**3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0],
                mt**3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1],
            ))

    def quad(p0, p1, p2):
        for k in range(1, 33):
            t = k / 32
            mt = 1 - t
            pts.append((
                mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
                mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1],
            ))

    for cmd, nums in seq:
        lc = cmd.lower()
        if lc == "a":
            raise ValueError("arc commands are not supported on a moving layer")
        rel = cmd.islower()
        n = arity[lc]
        if lc == "z":
            x, y = sx, sy
            pts.append((x, y))
            last_ctrl = last_q = None
            continue
        if n == 0 or len(nums) % n or not nums:
            raise ValueError(f"wrong number of values for path command {cmd}")
        for k in range(0, len(nums), n):
            a = nums[k : k + n]
            ox, oy = (x, y) if rel else (0.0, 0.0)
            if lc == "m":
                x, y = ox + a[0], oy + a[1]
                if k == 0:
                    sx, sy = x, y
                pts.append((x, y))
                last_ctrl = last_q = None
            elif lc == "l":
                x, y = ox + a[0], oy + a[1]
                pts.append((x, y))
                last_ctrl = last_q = None
            elif lc == "h":
                x = (x if rel else 0.0) + a[0]
                pts.append((x, y))
                last_ctrl = last_q = None
            elif lc == "v":
                y = (y if rel else 0.0) + a[0]
                pts.append((x, y))
                last_ctrl = last_q = None
            elif lc == "c":
                p1 = (ox + a[0], oy + a[1])
                p2 = (ox + a[2], oy + a[3])
                p3 = (ox + a[4], oy + a[5])
                cubic((x, y), p1, p2, p3)
                last_ctrl, last_q = p2, None
                x, y = p3
            elif lc == "s":
                p1 = (2 * x - last_ctrl[0], 2 * y - last_ctrl[1]) if last_ctrl else (x, y)
                p2 = (ox + a[0], oy + a[1])
                p3 = (ox + a[2], oy + a[3])
                cubic((x, y), p1, p2, p3)
                last_ctrl, last_q = p2, None
                x, y = p3
            elif lc == "q":
                p1 = (ox + a[0], oy + a[1])
                p2 = (ox + a[2], oy + a[3])
                quad((x, y), p1, p2)
                last_q, last_ctrl = p1, None
                x, y = p2
            elif lc == "t":
                p1 = (2 * x - last_q[0], 2 * y - last_q[1]) if last_q else (x, y)
                p2 = (ox + a[0], oy + a[1])
                quad((x, y), p1, p2)
                last_q, last_ctrl = p1, None
                x, y = p2
            if lc == "m":
                lc = "l"  # implicit lineto after the first moveto pair
                n = 2
    return pts


# --------------------------------------------------------------------------
# CSS animation model


@dataclass
class Animation:
    selector: str
    name: str
    duration_s: float | None
    iterations: str


def parse_animation_shorthand(value: str) -> list[tuple[str | None, float | None, str]]:
    out = []
    value = re.sub(r"(cubic-bezier|steps)\([^)]*\)", " ", value, flags=re.I)
    for one in value.split(","):
        name, duration, iters = None, None, "1"
        for tok in one.split():
            low = tok.lower().replace("!important", "")
            if not low:
                continue
            m = TIME_RE.match(low)
            if m:
                if duration is None:
                    num = float(m.group(1))
                    duration = num / 1000 if m.group(2).lower() == "ms" else num
                continue
            if low == "infinite":
                iters = "infinite"
                continue
            if re.fullmatch(r"\d{1,6}(?:\.\d{1,6})?|\.\d{1,6}", low):
                iters = low
                continue
            if low in ANIMATION_KEYWORDS:
                continue
            name = tok
        out.append((name, duration, iters))
    return out


def selector_matches(selector: str, el: ET.Element) -> bool:
    sel = selector.strip()
    if not sel or len(sel) > 200:
        raise ValueError(f"unsupported selector {selector!r} in an animation rule")
    split = len(sel) - len(sel.lstrip("*abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"))
    tag, rest = sel[:split] or None, sel[split:]
    if tag and not re.fullmatch(r"\*|[a-zA-Z][\w-]{0,40}", tag):
        raise ValueError(f"unsupported selector {selector!r} in an animation rule")
    if "".join(k + n for k, n in re.findall(r"([.#])([\w-]{1,80})", rest)) != rest:
        raise ValueError(f"unsupported selector {selector!r} in an animation rule")
    if tag and tag != "*" and local_name(el.tag) != tag.lower():
        return False
    classes = (el.get("class") or "").split()
    for kind, name in re.findall(r"([.#])([\w-]+)", rest):
        if kind == "." and name not in classes:
            return False
        if kind == "#" and el.get("id") != name:
            return False
    return True


def parse_transform(value: str) -> tuple[float, float]:
    """Return (tx, ty) in px for translate-only transforms; raise otherwise."""
    tx = ty = 0.0
    value = value.strip()
    if value.lower() == "none":
        return 0.0, 0.0
    func_re = r"\b([a-zA-Z][a-zA-Z0-9]{0,15})\(([^)]{0,200})\)"
    funcs = re.findall(func_re, value)
    if not funcs or re.sub(func_re, "", value).strip():
        raise ValueError(f"unparseable transform {value!r}")
    for fname, args in funcs:
        fname = fname.lower()
        parts = [p for p in re.split(r"[\s,]+", args.strip()) if p]
        vals = []
        for p in parts:
            m = re.fullmatch(r"(-?\d*\.?\d+)(px)?", p.lower())
            if not m:
                raise ValueError(f"transform value {p!r} is not px")
            vals.append(float(m.group(1)))
        if fname == "translate" and len(vals) in (1, 2):
            tx += vals[0]
            ty += vals[1] if len(vals) == 2 else 0.0
        elif fname == "translatex" and len(vals) == 1:
            tx += vals[0]
        elif fname == "translatey" and len(vals) == 1:
            ty += vals[0]
        else:
            raise ValueError(f"transform {fname}() is not allowed in a banner animation")
    return tx, ty


# --------------------------------------------------------------------------
# main lint


def _check_css_hazards(res: LintResult, where: str, text: str) -> None:
    """Refuse backslashes and the substrings that can load something external."""
    clean = normalize_css(text)
    if "\\" in clean:
        res.add("css-escape", f"{where} contains a backslash")
    flat = squash(clean)
    for needle in CSS_FORBIDDEN_SUBSTRINGS:
        if needle in flat:
            res.add("css-forbidden", f"{where} contains {needle!r}")


def _check_attr_value(res: LintResult, where: str, attr: str, value: str) -> None:
    _check_css_hazards(res, f"{where} @{attr}", value)
    value = normalize_css(value)
    low = value.lower()
    if "javascript:" in squash(low) or "vbscript:" in squash(low):
        res.add("script-url", f"{where} @{attr} contains a script URL")
    if "url(" in low:
        if len(re.findall(r"url\(", low)) != len(URL_FRAGMENT_ONLY.findall(value)):
            res.add("external-url", f"{where} @{attr} has a url() that is not #fragment")


def _check_css_text(res: LintResult, where: str, css: str) -> None:
    _check_css_hazards(res, where, css)
    css = normalize_css(css)
    low = squash(css)
    if "@import" in low:
        res.add("css-import", f"{where} uses @import")
    if "expression(" in low or "javascript:" in low or "-moz-binding" in low or "behavior:" in low:
        res.add("css-active", f"{where} contains active CSS (expression/javascript/binding)")
    if "url(" in css.lower():
        if len(re.findall(r"url\(", css.lower())) != len(URL_FRAGMENT_ONLY.findall(css)):
            res.add("external-url", f"{where} has a url() that is not #fragment")


def lint_text(
    text: str,
    name: str = "<svg>",
    *,
    profile: str = "banner",
    require_opaque_background: bool = False,
    min_bytes: int = DEFAULT_MIN_BYTES,
    expect: dict[str, int] | None = None,
    size_bytes: int | None = None,
    max_bytes: int | None = None,
) -> LintResult:
    res = LintResult(name)
    size = size_bytes if size_bytes is not None else len(text.encode("utf-8"))
    res.metrics["bytes"] = size
    if size < min_bytes:
        res.add("too-small", f"{size} bytes is below the {min_bytes}-byte minimum")
    if max_bytes is not None and size > max_bytes:
        res.add("too-large", f"{size} bytes is above the {max_bytes}-byte maximum")

    decoded = html.unescape(text)
    if re.search(r"<!\s*(doctype|entity)", decoded, re.I):
        res.add("doctype", "DOCTYPE/ENTITY declarations are not allowed")
        return res
    if PROCESSING_INSTRUCTION_RE.search(text) or PROCESSING_INSTRUCTION_RE.search(decoded):
        res.add("processing-instruction", "only a leading <?xml ...?> declaration is allowed")
        return res
    low_decoded = squash(decoded)
    if "<script" in low_decoded:
        res.add("script", "script markup found")
    if "javascript:" in low_decoded:
        res.add("script-url", "a javascript: URL appears in the file")

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        res.add("xml", f"not well-formed XML ({exc})")
        return res

    if local_name(root.tag) != "svg":
        res.add("root", f"root element is <{local_name(root.tag)}>, expected <svg>")
        return res

    vb = (root.get("viewBox") or "").replace(",", " ").split()
    try:
        vx, vy, vw, vh = (float(v) for v in vb)
        if vw <= 0 or vh <= 0:
            raise ValueError
    except ValueError:
        res.add("viewbox", "root needs a numeric viewBox 'minx miny width height'")
        return res
    res.metrics["viewbox"] = (vx, vy, vw, vh)

    parent: dict[ET.Element, ET.Element] = {}
    counts: dict[str, int] = {}
    css_parts: list[str] = []
    for el in root.iter():
        tag = local_name(el.tag)
        counts[tag] = counts.get(tag, 0) + 1
        for child in el:
            parent[child] = el
        if tag in FORBIDDEN_ELEMENTS:
            res.add("forbidden-element", f"<{tag}> is not allowed")
        if tag == "style":
            css_parts.append("".join(el.itertext()))
        for attr, value in el.attrib.items():
            aname = local_name(attr)
            where = f"<{tag}>"
            if aname.startswith("on"):
                res.add("event-handler", f"{where} has event attribute @{aname}")
            if aname in ("href", "src") and not value.strip().startswith("#"):
                res.add("external-href", f"{where} @{aname} is not a #fragment")
            _check_attr_value(res, where, aname, value)
            if aname == "style":
                _check_css_text(res, f"{where} @style", value)
                if re.search(r"(^|;)\s*animation", value, re.I):
                    res.add("inline-animation", f"{where} declares animation inline")

    # expected elements
    exp = dict(expect or {})
    if profile == "banner":
        exp.setdefault("text", 1)
    for tag, n in exp.items():
        if counts.get(tag.lower(), 0) < n:
            res.add("expected-element", f"needs at least {n} <{tag}>, found {counts.get(tag.lower(), 0)}")

    # stylesheet
    css = strip_css_comments("\n".join(css_parts))
    _check_css_text(res, "<style>", css)
    try:
        blocks = parse_blocks(css)
    except ValueError as exc:
        res.add("css", str(exc))
        blocks = []

    keyframes: dict[str, list[tuple[str, list[tuple[str, str]]]]] = {}
    rules: list[tuple[str, list[tuple[str, str]]]] = []
    reduced_motion_ok = False
    for prelude, body in blocks:
        low = prelude.lower()
        if low.startswith("@keyframes") or low.startswith("@-webkit-keyframes"):
            kname = prelude.split(None, 1)[1].strip() if len(prelude.split()) > 1 else ""
            try:
                keyframes[kname] = [(sel, parse_decls(b)) for sel, b in parse_blocks(body)]
            except ValueError as exc:
                res.add("css", str(exc))
        elif low.startswith("@media"):
            try:
                inner = parse_blocks(body)
            except ValueError as exc:
                res.add("css", str(exc))
                continue
            if REDUCED_MOTION_MEDIA.match(prelude.strip()):
                for sel, b in inner:
                    if sel.strip() == "*" and "animation:none!important" in squash(b):
                        reduced_motion_ok = True
            else:
                rules.extend((sel, parse_decls(b)) for sel, b in inner)
        elif low.startswith("@"):
            res.add("css-at-rule", f"unsupported at-rule {prelude.split()[0]!r}")
        else:
            rules.append((prelude, parse_decls(body)))

    animations: list[Animation] = []
    for sel, decls in rules:
        names: list[str | None] = []
        durations: list[float | None] = []
        iters: list[str] = []
        for prop, value in decls:
            if prop == "animation":
                for nm, du, it in parse_animation_shorthand(value):
                    names.append(nm)
                    durations.append(du)
                    iters.append(it)
            elif prop == "animation-name":
                names = [v.strip() for v in value.split(",")]
            elif prop == "animation-duration":
                durations = []
                for v in value.split(","):
                    m = TIME_RE.match(v.strip().lower())
                    durations.append(
                        (float(m.group(1)) / (1000 if m.group(2) == "ms" else 1)) if m else None
                    )
            elif prop == "animation-iteration-count":
                iters = [v.strip().lower() for v in value.split(",")]
        for i, nm in enumerate(names):
            if nm is None or nm.lower() == "none":
                continue
            animations.append(Animation(
                selector=sel,
                name=nm,
                duration_s=durations[i] if i < len(durations) else None,
                iterations=iters[i] if i < len(iters) else "1",
            ))

    animated = bool(keyframes) or bool(animations)
    res.metrics["animated"] = animated
    if animated and not reduced_motion_ok:
        res.add(
            "reduced-motion",
            "animated SVG lacks @media (prefers-reduced-motion: reduce){*{animation:none!important}}",
        )
    if animated and Path(name).name.lower().endswith("-static.svg"):
        res.add("static-twin", "a -static.svg file must not contain animation")

    if profile == "banner":
        if vw > MAX_BANNER_WIDTH:
            res.add("banner-width", f"viewBox width {vw:g} > {MAX_BANNER_WIDTH:g}")
        if vh < MIN_BANNER_HEIGHT:
            res.add("banner-height", f"viewBox height {vh:g} < {MIN_BANNER_HEIGHT:g}")
        if animated:
            _check_motion(res, root, parent, keyframes, animations, vh)

    if require_opaque_background:
        _check_background(res, root, vx, vy, vw, vh)
    return res


def _check_motion(res, root, parent, keyframes, animations, vh) -> None:
    limit = min(MAX_AMPLITUDE_PX, MAX_AMPLITUDE_FRACTION * vh)
    res.metrics["amplitude_limit_px"] = round(limit, 3)
    if len(animations) > MAX_ANIMATIONS:
        res.add("loops", f"{len(animations)} animations found; at most {MAX_ANIMATIONS} loop is allowed")
    infinite = [a for a in animations if a.iterations == "infinite"]
    if len(infinite) > 1:
        res.add("loops", f"{len(infinite)} infinite loops found; only one is allowed")
    for kname, frames in keyframes.items():
        for sel, decls in frames:
            for prop, _ in decls:
                if prop not in ("transform", "animation-timing-function"):
                    res.add("flashing", f"@keyframes {kname} changes {prop!r}; only transform may change")

    worst_amp, periods = 0.0, []
    for anim in animations:
        if anim.duration_s is None or anim.duration_s <= 0:
            res.add("period", f"animation {anim.name} has no positive duration")
        else:
            periods.append(anim.duration_s)
            if anim.duration_s < MIN_PERIOD_S:
                res.add("period", f"animation {anim.name} period {anim.duration_s:g}s < {MIN_PERIOD_S:g}s")
        frames = keyframes.get(anim.name)
        if frames is None:
            res.add("keyframes", f"animation {anim.name} has no @keyframes")
            continue
        xs, ys = [0.0], [0.0]
        for sel, decls in frames:
            for prop, value in decls:
                if prop != "transform":
                    continue
                try:
                    tx, ty = parse_transform(value)
                except ValueError as exc:
                    res.add("transform", f"@keyframes {anim.name}: {exc}")
                    continue
                xs.append(tx)
                ys.append(ty)
        vertical = max(abs(v) for v in ys)
        drifts = max(xs) - min(xs) > 0
        try:
            targets = [el for el in root.iter() if selector_matches(anim.selector, el)]
        except ValueError as exc:
            res.add("selector", str(exc))
            continue
        if not targets:
            res.add("selector", f"animation rule {anim.selector!r} matches no element")
        shape_half = 0.0
        for el in targets:
            for d in el.iter():
                tag = local_name(d.tag)
                if tag in TEXT_ELEMENTS:
                    res.add("text-moves", "text sits on a moving layer; name text must be static")
                elif tag not in MOVING_LAYER_ALLOWED:
                    res.add("moving-layer", f"<{tag}> on a moving layer; only g and path are allowed")
                if d.get("transform") is not None:
                    res.add("moving-layer", f"<{tag}> on a moving layer has a transform attribute")
                if tag == "path" and drifts:
                    try:
                        pts = path_points(d.get("d") or "")
                    except ValueError as exc:
                        res.add("path", f"moving path: {exc}")
                        continue
                    if pts:
                        ext = max(p[1] for p in pts) - min(p[1] for p in pts)
                        shape_half = max(shape_half, ext / 2)
        amp = vertical + shape_half
        worst_amp = max(worst_amp, amp)
        if amp > limit + 1e-9:
            res.add("amplitude", f"animation {anim.name} amplitude {amp:.2f}px > {limit:.2f}px")
    res.metrics["amplitude_px"] = round(worst_amp, 3)
    if periods:
        res.metrics["period_s"] = min(periods)


def _opaque_fill(el: ET.Element) -> str | None:
    style = {k: v for k, v in parse_decls(el.get("style") or "")}
    fill = style.get("fill", el.get("fill"))
    for key in ("opacity", "fill-opacity"):
        val = style.get(key, el.get(key))
        if val is not None:
            try:
                if float(val) < 1:
                    return None
            except ValueError:
                return None
    if not fill:
        return None
    fill = fill.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{3}|#[0-9a-f]{6}", fill):
        return fill
    if re.fullmatch(r"#[0-9a-f]{8}", fill) and fill.endswith("ff"):
        return fill[:7]
    return None


def _check_background(res, root, vx, vy, vw, vh) -> None:
    first = next((c for c in root if local_name(c.tag) not in NON_DRAWING), None)
    if first is None or local_name(first.tag) != "rect":
        res.add("background", "first drawable child must be an opaque full-size <rect>")
        return

    def num(attr: str, default: float, full: float) -> float | None:
        raw = (first.get(attr) or "").strip()
        if not raw:
            return default
        if raw == "100%":
            return full
        try:
            return float(raw.removesuffix("px"))
        except ValueError:
            return None

    x, y = num("x", 0.0, 0.0), num("y", 0.0, 0.0)
    w, h = num("width", -1, vw), num("height", -1, vh)
    if None in (x, y, w, h) or x > vx or y > vy or x + w < vx + vw or y + h < vy + vh:
        res.add("background", "background <rect> does not cover the whole viewBox")
    if first.get("transform"):
        res.add("background", "background <rect> must not be transformed")
    fill = _opaque_fill(first)
    if fill is None:
        res.add("background", "background <rect> needs a solid opaque hex fill")
    else:
        res.metrics["background"] = fill


def lint_file(path: str | Path, **kwargs) -> LintResult:
    p = Path(path)
    if p.is_symlink():
        r = LintResult(str(path))
        r.add("symlink", "refusing to lint a symlink")
        return r
    try:
        raw = p.read_bytes()
    except OSError as exc:
        r = LintResult(str(path))
        r.add("missing", f"cannot read file ({exc.strerror})")
        return r
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        r = LintResult(str(path))
        r.add("encoding", "file is not UTF-8")
        return r
    return lint_text(text, str(path), size_bytes=len(raw), **kwargs)


def _parse_expect(values: list[str]) -> dict[str, int]:
    out = {}
    for v in values:
        tag, _, n = v.partition("=")
        if not re.fullmatch(r"[A-Za-z][\w-]*", tag) or (n and not n.isdigit()):
            raise argparse.ArgumentTypeError(f"bad --expect {v!r}; use TAG or TAG=N")
        out[tag.lower()] = int(n) if n else 1
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Lint profile SVG assets.")
    ap.add_argument("files", nargs="+", metavar="FILE")
    ap.add_argument("--require-opaque-background", action="store_true")
    ap.add_argument("--profile", choices=("banner", "chart"), default="banner")
    ap.add_argument("--min-bytes", type=int, default=DEFAULT_MIN_BYTES)
    ap.add_argument("--max-bytes", type=int, default=None)
    ap.add_argument("--expect", action="append", default=[], metavar="TAG[=N]")
    args = ap.parse_args(argv)
    try:
        expect = _parse_expect(args.expect)
    except argparse.ArgumentTypeError as exc:
        ap.error(str(exc))

    bad = 0
    for f in args.files:
        r = lint_file(
            f,
            profile=args.profile,
            require_opaque_background=args.require_opaque_background,
            min_bytes=args.min_bytes,
            max_bytes=args.max_bytes,
            expect=expect,
        )
        if r.ok:
            m = r.metrics
            extra = ""
            if m.get("animated") and "amplitude_px" in m:
                extra = (
                    f", amplitude {m['amplitude_px']:g}px <= {m['amplitude_limit_px']:g}px"
                    f", period {m.get('period_s', 0):g}s"
                )
            print(f"OK   {f} ({m['bytes']} bytes, {'animated' if m.get('animated') else 'static'}{extra})")
        else:
            bad += 1
            for v in r.violations:
                print(f"FAIL {f}: {v}")
    print(f"lint_svg: {len(args.files)} file(s) checked, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
