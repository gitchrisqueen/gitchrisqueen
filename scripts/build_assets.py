#!/usr/bin/env python3
"""Build the profile's hand-designed SVG assets from data files.

Usage:
    python scripts/build_assets.py            # write assets/*.svg
    python scripts/build_assets.py --check    # exit 1 if a committed file differs

Outputs (all opaque-background, no script, no external reference):
    assets/skills-build.svg, assets/skills-ai.svg   tool logos, two panels
    assets/gate-animated.svg, assets/gate-static.svg  the compiler-gate terminal
    assets/card-<id>.svg                              one card per project

Every text-bearing image is at most 520 units wide, so a phone column scales
it by no less than about 0.6 and the smallest text stays near 9 px.

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
# Brand colours that sit too dark on the tile are replaced by a lighter tint.
TINT = {"mysql": "#8bb8d9"}


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


def glyph_colour(slug: str, brand_hex: str, bg: str) -> str:
    """The brand colour when it reads on the tile, else the light text colour."""
    colour = TINT.get(slug, "#" + brand_hex.lower())
    if contrast(colour, bg) < 3.0:
        colour = TEXT
    return colour


# ---------------------------------------------------------------- helpers

def svg_open(width: int, height: int, title: str, desc: str, extra_css: str = "") -> list[str]:
    css = f"text{{font-family:{SANS}}}.m{{font-family:{MONO}}}" + extra_css
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
    colour = glyph_colour(slug, icon["hex"], bg)
    scale = size / 24
    path = escape(icon["path"], {'"': "&quot;"})
    return (f'<g transform="translate({x:g} {y:g}) scale({scale:.4f})" fill="{colour}">'
            f'<path d="{path}"/></g>')


# ---------------------------------------------------------------- skills

# (panel id, title, [(slug or "mono:XX", label)])
SKILL_PANELS = [
    ("skills-build", "Languages and services", [
        ("python", "Python"), ("javascript", "JavaScript"), ("swift", "Swift"), ("nodedotjs", "Node.js"),
        ("fastapi", "FastAPI"), ("celery", "Celery"), ("redis", "Redis"), ("mysql", "MySQL"),
    ]),
    ("skills-ai", "AI, interface, test and ship", [
        ("langchain", "LangChain"), ("mono:Li", "LiteLLM"), ("mono:OR", "OpenRouter"), ("react", "React"),
        ("streamlit", "Streamlit"), ("selenium", "Selenium"), ("docker", "Docker"), ("githubactions", "Actions"),
    ]),
]
SKILL_FULL_NAMES = {"Actions": "GitHub Actions"}


def build_skills(panel_id: str, icons: dict) -> str:
    title, items = next((t, i) for p, t, i in SKILL_PANELS if p == panel_id)
    width, tile_w, tile_h, gap, left = 392, 84, 72, 8, 16
    height = 48 + 2 * (tile_h + gap) + 8
    names = [SKILL_FULL_NAMES.get(label, label) for _, label in items]
    out = svg_open(width, height, title, "Tools used in the projects on this page: " + ", ".join(names) + ".")
    require_text_contrast(GOLD, BG, "skills panel title")
    require_text_contrast(TEXT, TILE, "skills tile label")
    out.append(f'<text x="{left}" y="28" font-size="14" font-weight="700" fill="{GOLD}">{escape(title)}</text>')
    for n, (slug, label) in enumerate(items):
        x = left + (n % 4) * (tile_w + gap)
        y = 44 + (n // 4) * (tile_h + gap)
        out.append(f'<rect x="{x}" y="{y}" width="{tile_w}" height="{tile_h}" rx="10" fill="{TILE}" stroke="{LINE}"/>')
        if slug.startswith("mono:"):
            out.append(f'<rect x="{x + 28}" y="{y + 9}" width="28" height="28" rx="7" fill="{GOLD}"/>')
            out.append(f'<text x="{x + 42}" y="{y + 29}" text-anchor="middle" font-size="13" font-weight="800" '
                       f'fill="{BG}">{escape(slug[5:])}</text>')
        else:
            out.append(icon_group(icons, slug, x + 28, y + 9, 28, TILE))
        out.append(f'<text x="{x + tile_w / 2:g}" y="{y + 58}" text-anchor="middle" font-size="13" '
                   f'fill="{TEXT}">{escape(label)}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- gate terminal

GATE_LINES = [
    # (text, fill, x offset)
    ("$ grade submission.cpp", GOLD, 0),
    ('LLM verdict: "does not compile"', TEXT, 0),
    ("wrong: the code is valid", RED, 20),
    ("$ compile submission.cpp", GOLD, 0),
    ("compiler exit code: 0", TEXT, 0),
    ("verdict: compiles, grade stands", GREEN, 0),
]
GATE_CYCLE = 18.0
GATE_START = [0.6, 2.2, 3.4, 5.6, 7.2, 8.8]
GATE_HIDE = 16.4


def build_gate(animated: bool) -> str:
    width, height = 520, 290
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
        "then returns exit code 0, so the grade stands.",
        css)
    out.append(f'<rect x="8" y="8" width="504" height="274" rx="12" fill="{TILE}" stroke="{LINE}"/>')
    for i, col in enumerate((RED, GOLD, GREEN)):
        out.append(f'<circle cx="{30 + i * 20}" cy="30" r="6" fill="{col}"/>')
    out.append(f'<text x="260" y="35" text-anchor="middle" font-size="13" fill="{MUTED}">'
               f'the compiler gate (illustration)</text>')
    require_text_contrast(MUTED, TILE, "gate window title")
    y = 78
    for i, (text, fill, dx) in enumerate(GATE_LINES):
        require_text_contrast(fill, TILE, f"gate line {i}")
        cls = f"m l{i}" if animated else "m"
        out.append(f'<text class="{cls}" x="{30 + dx}" y="{y}" font-size="18" fill="{fill}" '
                   f'xml:space="preserve">{escape(text)}</text>')
        y += 36
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- cards

CARDS = [
    {
        "id": "lem", "tag": "Live web app", "title": "LinkedIn Engagement Manager",
        "lines": ["Builds a 30-day content plan, gates AI-written", "posts on quality, caps daily engagement."],
        "label": "What broke",
        "broke": ["The live app sat behind new releases for a day,",
                  "inside a green run. An hourly check now flags it."],
        "icons": ["fastapi", "celery", "redis", "mysql", "react", "docker"],
    },
    {
        "id": "cpcc", "tag": "Instructor admin tool", "title": "CPCC Task Automation",
        "lines": ["Attendance, withdrawals and rubric grading for", "my own courses, with a human review step."],
        "label": "What broke",
        "broke": ["The model called valid C++ \"does not compile\".", "A real compiler now makes that call."],
        "icons": ["python", "streamlit", "selenium", "langchain"],
    },
    {
        "id": "hearing", "tag": "Speaker identification", "title": "hearing-copilot",
        "lines": ["Labels who is speaking in a live transcript.", "Scored offline on real oral-argument audio."],
        "label": "Limits",
        "broke": ["The headline score comes from one hearing, with",
                  "no confidence interval. Caveats are in RESULTS.md."],
        "icons": ["javascript", "nodedotjs"],
    },
    {
        "id": "panthera", "tag": "Paper trading experiment", "title": "panthera",
        "lines": ["MLB picks graded against pre-registered rules.",
                  "Paper trading only; the ROI is a screen, not proof."],
        "label": "What broke",
        "broke": ["A config whitelist skipped the postseason and",
                  "14 slate days passed unnoticed. A health check", "now flags it."],
        "icons": ["python", "githubactions"],
    },
]


def build_card(card: dict, icons: dict) -> str:
    width = 392
    broke_lines = card["broke"]
    height = 252 + 20 * (len(broke_lines) - 2)
    out = svg_open(width, height, card["title"],
                   f'{card["title"]}. {" ".join(card["lines"])} {card["label"]}: {" ".join(broke_lines)}')
    out.append(f'<defs><clipPath id="r"><rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="12"/>'
               f'</clipPath></defs>')
    out.append(f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="12" fill="{TILE}" stroke="{LINE}"/>')
    out.append(f'<rect x="1" y="1" width="6" height="{height - 2}" fill="{GOLD}" clip-path="url(#r)"/>')
    for fg, where in ((GOLD, "card tag"), (TEXT, "card title"), (MUTED, "card body")):
        require_text_contrast(fg, TILE, where)
    out.append(f'<text x="26" y="34" font-size="13" fill="{GOLD}">{escape(card["tag"])}</text>')
    out.append(f'<text x="26" y="64" font-size="22" font-weight="700" fill="{TEXT}">{escape(card["title"])}</text>')
    y = 92
    for line in card["lines"]:
        out.append(f'<text x="26" y="{y}" font-size="13.5" fill="{MUTED}">{escape(line)}</text>')
        y += 20
    out.append(f'<line x1="26" y1="{y + 4}" x2="{width - 26}" y2="{y + 4}" stroke="{LINE}"/>')
    out.append(f'<text x="26" y="{y + 28}" font-size="13" font-weight="700" fill="{GOLD}">'
               f'{escape(card["label"])}</text>')
    y += 50
    for line in broke_lines:
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
    files = {f"{panel}.svg": build_skills(panel, icons) for panel, _, _ in SKILL_PANELS}
    files["gate-animated.svg"] = build_gate(True)
    files["gate-static.svg"] = build_gate(False)
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
