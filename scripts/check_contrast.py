#!/usr/bin/env python3
"""Check every declared colour pair against WCAG 2.x contrast minimums.

Usage:
    python scripts/check_contrast.py assets/colors.json

Exit status: 0 when every non-exempt pair passes, 1 when any pair fails or
the file is malformed, 2 on a usage error.

Schema of the colours file (JSON object):

    {
      "version": 1,
      "pairs": [
        {
          "id":         "header-name",          # unique, [a-z0-9-]+
          "kind":       "text" | "graphic",     # text needs >= 4.5:1,
                                                 # graphic needs >= 3:1
          "foreground": "#e9d437",              # #rgb or #rrggbb, opaque
          "background": "#0d1117",              # #rgb or #rrggbb, opaque
          "where":      "assets/header-*.svg: name",   # free text, optional
          "exempt":     true,                   # optional; skips the check
          "reason":     "why it is exempt"      # required when exempt
        }
      ]
    }

`kind: "text"` covers any glyphs a reader must read (SVG text, badge labels
and values). `kind: "graphic"` covers non-text parts that carry meaning
(WCAG 1.4.11), such as the contribution-calendar cells for levels 1-4.
An exempt pair is reported but not checked; it must say why (for example
the empty level-0 calendar cell, which carries no information).

The ratio is (L1 + 0.05) / (L2 + 0.05) with relative luminance from the
sRGB transfer function in WCAG 2.2. Ratios are printed to two decimals; the
comparison uses the unrounded value.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MINIMUMS = {"text": 4.5, "graphic": 3.0}
HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def parse_hex(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not HEX_RE.fullmatch(value):
        raise ValueError(f"colour {value!r} is not #rgb or #rrggbb")
    h = value[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def relative_luminance(value: str) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = parse_hex(value)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def check(data: object) -> tuple[list[dict], list[str]]:
    """Return (rows, errors). Each row has id, kind, ratio, minimum, status."""
    errors: list[str] = []
    rows: list[dict] = []
    if not isinstance(data, dict) or not isinstance(data.get("pairs"), list):
        return rows, ["top level must be an object with a 'pairs' list"]
    if not data["pairs"]:
        return rows, ["'pairs' is empty"]
    seen: set[str] = set()
    for i, pair in enumerate(data["pairs"]):
        label = f"pairs[{i}]"
        if not isinstance(pair, dict):
            errors.append(f"{label}: not an object")
            continue
        pid = pair.get("id")
        if not isinstance(pid, str) or not ID_RE.fullmatch(pid):
            errors.append(f"{label}: 'id' must match [a-z0-9-]+")
            continue
        label = pid
        if pid in seen:
            errors.append(f"{label}: duplicate id")
            continue
        seen.add(pid)
        kind = pair.get("kind")
        if kind not in MINIMUMS:
            errors.append(f"{label}: 'kind' must be 'text' or 'graphic'")
            continue
        try:
            ratio = contrast_ratio(pair.get("foreground"), pair.get("background"))
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            continue
        exempt = pair.get("exempt", False)
        if exempt not in (True, False):
            errors.append(f"{label}: 'exempt' must be true or false")
            continue
        if exempt:
            if kind == "text":
                errors.append(f"{label}: text pairs cannot be exempt")
                continue
            if not isinstance(pair.get("reason"), str) or not pair["reason"].strip():
                errors.append(f"{label}: an exempt pair needs a 'reason'")
                continue
        minimum = MINIMUMS[kind]
        status = "EXEMPT" if exempt else ("PASS" if ratio >= minimum else "FAIL")
        rows.append({
            "id": pid,
            "kind": kind,
            "foreground": pair["foreground"].lower(),
            "background": pair["background"].lower(),
            "ratio": ratio,
            "minimum": minimum,
            "status": status,
        })
        if status == "FAIL":
            errors.append(f"{label}: {ratio:.2f}:1 is below {minimum}:1 for {kind}")
    return rows, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WCAG contrast check for declared colour pairs.")
    ap.add_argument("colors", metavar="COLORS_JSON")
    args = ap.parse_args(argv)
    try:
        data = json.loads(Path(args.colors).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"check_contrast: cannot read {args.colors}: {exc}")
        return 1
    rows, errors = check(data)
    for r in rows:
        print(
            f"{r['status']:<6} {r['id']:<28} {r['kind']:<7} "
            f"{r['foreground']} on {r['background']}  {r['ratio']:.2f}:1 (min {r['minimum']}:1)"
        )
    for e in errors:
        print(f"ERROR  {e}")
    checked = sum(1 for r in rows if r["status"] != "EXEMPT")
    print(f"check_contrast: {checked} pair(s) checked, {len(rows) - checked} exempt, {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
