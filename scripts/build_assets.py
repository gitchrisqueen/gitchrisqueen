#!/usr/bin/env python3
"""Build the profile's hand-designed SVG assets from data files.

Usage:
    python scripts/build_assets.py            # write assets/*.svg
    python scripts/build_assets.py --check    # exit 1 if a committed file differs

Outputs (all opaque-background, no script, no external reference):
    assets/skills.svg            tool logos, three rows
    assets/gate-animated.svg     the compiler-gate terminal, one slow loop
    assets/gate-static.svg       same terminal, every line visible, no motion
    assets/card-<id>.svg         one card per project

Only the Python standard library is used. Logo paths come from
data/icons.json (simple-icons, CC0). Text on every asset is checked against
its background for WCAG contrast; the build fails below 4.5:1 for text and
below 3:1 for logo glyphs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
BG = "#0d1117"
TILE = "#161b22"
LINE = "#30363d"
GOLD = "#e9d437"
TEXT = "#e6edf3"
MUTED = "#9ba7b4"
RED = "#ff7b72"
GREEN = "#3fb950"
SANS = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"
REDUCED = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"


# ---------------------------------------------------------------- contrast

def _lin(c: int) -> float:
    v = c / 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def require_text_contrast(fg: str, bg: str, where: str) -> None:
    ratio = contrast(fg, bg)
    if ratio < 4.5:
        raise SystemExit(f"contrast {ratio:.2f}:1 for {where} ({fg} on {bg}) is below 4.5:1")


def glyph_colour(brand_hex: str, bg: str) -> str:
    """The brand colour when it reads on the tile, else the light text colour."""
    brand = "#" + brand_hex.lower()
    return brand if contrast(brand, bg) >= 3.0 else TEXT


# ---------------------------------------------------------------- helpers

def svg_open(width: int, height: int, title: str, desc: str, extra_css: str = "") -> list[str]:
    css = (f"text{{font-family:{SANS}}}.m{{font-family:{MONO}}}" + extra_css)
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img">',
        f"<title>{escape(title)}</title>",
        f"<desc>{escape(desc)}</desc>",
        f"<style>{css}</style>",
        f'<rect width="{width}" height="{height}" fill="{BG}"/>',
    ]


def load_icons() -> dict:
    return json.loads((ROOT / "data" / "icons.json").read_text(encoding="utf-8"))["icons"]


def icon_group(icons: dict, slug: str, x: float, y: float, size: float, bg: str) -> str:
    icon = icons[slug]
    colour = glyph_colour(icon["hex"], bg)
    scale = size / 24
    return (f'<g transform="translate({x:g} {y:g}) scale({scale:.4f})" fill="{colour}">'
            f'<path d="{icon["path"]}"/></g>')


# ---------------------------------------------------------------- skills

SKILL_ROWS = [
    ("Languages", ["python", "javascript", "swift"]),
    ("Services and UI", ["fastapi", "celery", "redis", "mysql", "nodedotjs", "react", "streamlit"]),
    ("LLM, test and ship", ["langchain", "text:LiteLLM", "text:OpenRouter", "selenium", "docker", "githubactions"]),
]


def build_skills(icons: dict) -> str:
    width, row_h, left, pitch = 800, 84, 200, 84
    height = 22 + row_h * len(SKILL_ROWS) + 6
    names = []
    for _, items in SKILL_ROWS:
        names.extend(icons[i]["title"] if not i.startswith("text:") else i[5:] for i in items)
    out = svg_open(width, height, "Tools I use",
                   "Tools used in the projects on this page: " + ", ".join(names) + ".")
    require_text_contrast(GOLD, BG, "skills row labels")
    require_text_contrast(TEXT, TILE, "skills tile labels")
    for r, (label, items) in enumerate(SKILL_ROWS):
        top = 22 + r * row_h
        out.append(f'<text x="24" y="{top + 44}" font-size="12" font-weight="700" fill="{GOLD}" '
                   f'letter-spacing="1">{escape(label.upper())}</text>')
        for c, item in enumerate(items):
            x = left + c * pitch
            out.append(f'<rect x="{x}" y="{top}" width="74" height="70" rx="10" fill="{TILE}" stroke="{LINE}"/>')
            if item.startswith("text:"):
                name = item[5:]
                fs = 14 if len(name) <= 7 else 11
                require_text_contrast(GOLD, TILE, "text tile glyph")
                out.append(f'<text x="{x + 37}" y="{top + 40}" text-anchor="middle" font-size="{fs}" '
                           f'font-weight="700" fill="{GOLD}">{escape(name)}</text>')
                continue
            out.append(icon_group(icons, item, x + 23, top + 11, 28, TILE))
            label_text = icons[item]["title"]
            fs = 11 if len(label_text) <= 9 else 9.5
            out.append(f'<text x="{x + 37}" y="{top + 60}" text-anchor="middle" font-size="{fs}" '
                       f'fill="{TEXT}">{escape(label_text)}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- gate terminal

GATE_LINES = [
    # (text, fill, trailing tag text, tag fill)
    ("$ grade submission.cpp", GOLD, None, None),
    ('LLM verdict: "does not compile"', TEXT, "  wrong: the code is valid", RED),
    ("$ compile submission.cpp", GOLD, None, None),
    ("compiler exit code: 0", TEXT, None, None),
    ("verdict: compiles. The grade stands.", GREEN, None, None),
]
GATE_CYCLE = 18.0
GATE_START = [0.6, 2.4, 5.2, 7.0, 9.0]
GATE_HIDE = 16.4


def build_gate(animated: bool) -> str:
    width, height = 800, 312
    css = ""
    if animated:
        rules = []
        for i, start in enumerate(GATE_START):
            a = start / GATE_CYCLE * 100
            b = (start + 0.5) / GATE_CYCLE * 100
            c = GATE_HIDE / GATE_CYCLE * 100
            d = (GATE_HIDE + 0.8) / GATE_CYCLE * 100
            rules.append(f"@keyframes g{i}{{0%,{a:.2f}%{{opacity:0}}{b:.2f}%,{c:.2f}%{{opacity:1}}"
                         f"{d:.2f}%,100%{{opacity:0}}}}.l{i}{{animation:g{i} {GATE_CYCLE:g}s linear infinite}}")
        css = "".join(rules) + REDUCED
    out = svg_open(
        width, height, "The compiler gate",
        "Illustration, not a recording. A language model first judges valid C++ as not compiling; a real compiler "
        "then returns exit code 0, so the grade stands. This is the check added in CPCC Task Automation.",
        css)
    out.append(f'<rect x="24" y="20" width="752" height="272" rx="12" fill="{TILE}" stroke="{LINE}"/>')
    for i, col in enumerate((RED, GOLD, GREEN)):
        out.append(f'<circle cx="{52 + i * 22}" cy="44" r="6" fill="{col}"/>')
    out.append(f'<text x="400" y="49" text-anchor="middle" font-size="12" fill="{MUTED}">'
               f'the compiler gate (illustration)</text>')
    require_text_contrast(MUTED, TILE, "gate window title")
    y = 92
    for i, (text, fill, tag, tag_fill) in enumerate(GATE_LINES):
        require_text_contrast(fill, TILE, f"gate line {i}")
        cls = f"m l{i}" if animated else "m"
        tag_svg = ""
        if tag:
            require_text_contrast(tag_fill, TILE, "gate tag")
            tag_svg = f'<tspan fill="{tag_fill}" font-weight="700">{escape(tag)}</tspan>'
        out.append(f'<text class="{cls}" x="52" y="{y}" font-size="18" fill="{fill}" xml:space="preserve">'
                   f'{escape(text)}{tag_svg}</text>')
        y += 36
    out.append(f'<text x="52" y="272" font-size="12" fill="{MUTED}">Illustration of the real-compiler check added in '
               f'CPCC Task Automation (pull request #267). Not a recording.</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- cards

CARDS = [
    {
        "id": "lem", "tag": "LIVE WEB APP", "title": "LinkedIn Engagement Manager",
        "lines": ["Builds a 30-day content plan, gates AI-written", "posts on quality, caps daily engagement."],
        "broke": ["The live app sat behind new releases for a day,", "inside a green run. An hourly check now flags it."],
        "icons": ["fastapi", "celery", "redis", "mysql", "react", "docker"],
    },
    {
        "id": "cpcc", "tag": "INSTRUCTOR ADMIN TOOL", "title": "CPCC Task Automation",
        "lines": ["Attendance, withdrawals and rubric grading for", "my own courses, with a human review step."],
        "broke": ["The model called valid C++ \"does not compile\".", "A real compiler now makes that call."],
        "icons": ["python", "streamlit", "selenium", "langchain"],
    },
    {
        "id": "hearing", "tag": "SPEAKER IDENTIFICATION", "title": "hearing-copilot",
        "lines": ["Labels who is speaking in a live transcript.", "Scored offline on real oral-argument audio."],
        "label": "LIMITS", "broke": ["One hearing, no confidence interval. The", "numbers and their caveats are in RESULTS.md."],
        "icons": ["javascript", "nodedotjs"],
    },
    {
        "id": "panthera", "tag": "PAPER TRADING EXPERIMENT", "title": "panthera",
        "lines": ["MLB picks graded against pre-registered rules.", "Paper trading only; no ROI claim."],
        "broke": ["A config whitelist skipped the postseason and", "14 days passed unnoticed. A health check now flags it."],
        "icons": ["python", "githubactions"],
    },
]


def build_card(card: dict, icons: dict) -> str:
    width, height = 392, 262
    out = svg_open(width, height, card["title"],
                   f'{card["title"]}. {" ".join(card["lines"])} What broke: {" ".join(card["broke"])}')
    out.append(f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="12" fill="{TILE}" stroke="{LINE}"/>')
    out.append(f'<rect x="1" y="1" width="6" height="{height - 2}" rx="3" fill="{GOLD}"/>')
    for fg, bg, where in ((GOLD, TILE, "card tag"), (TEXT, TILE, "card title"),
                          (MUTED, TILE, "card body"), (TEXT, TILE, "card broke")):
        require_text_contrast(fg, bg, where)
    out.append(f'<text x="26" y="34" font-size="11" font-weight="700" letter-spacing="1.4" fill="{GOLD}">'
               f'{escape(card["tag"])}</text>')
    out.append(f'<text x="26" y="64" font-size="22" font-weight="700" fill="{TEXT}">{escape(card["title"])}</text>')
    y = 92
    for line in card["lines"]:
        out.append(f'<text x="26" y="{y}" font-size="13.5" fill="{MUTED}">{escape(line)}</text>')
        y += 20
    out.append(f'<line x1="26" y1="{y + 4}" x2="{width - 26}" y2="{y + 4}" stroke="{LINE}"/>')
    out.append(f'<text x="26" y="{y + 28}" font-size="11" font-weight="700" letter-spacing="1.4" fill="{GOLD}">'
               f'{escape(card.get("label", "WHAT BROKE"))}</text>')
    y += 50
    for line in card["broke"]:
        out.append(f'<text x="26" y="{y}" font-size="13.5" fill="{TEXT}">{escape(line)}</text>')
        y += 20
    x = 26
    for slug in card["icons"]:
        out.append(icon_group(icons, slug, x, y + 2, 24, TILE))
        x += 34
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- main

def build_all() -> dict[str, str]:
    icons = load_icons()
    files = {
        "skills.svg": build_skills(icons),
        "gate-animated.svg": build_gate(True),
        "gate-static.svg": build_gate(False),
    }
    for card in CARDS:
        files[f"card-{card['id']}.svg"] = build_card(card, icons)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if a committed file differs")
    parser.add_argument("--out-dir", default=str(ROOT / "assets"))
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)
    files = build_all()
    bad = []
    for name, text in files.items():
        path = out_dir / name
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                bad.append(name)
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path} ({len(text)} bytes)")
    if bad:
        print("out of date: " + ", ".join(bad) + " (run scripts/build_assets.py)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
