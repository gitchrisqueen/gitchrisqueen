#!/usr/bin/env python3
"""Build the profile's hand-designed SVG assets from data files.

Usage:
    python scripts/build_assets.py            # write assets/*.svg
    python scripts/build_assets.py --check    # exit 1 if a committed file differs

Outputs (all opaque-background, no script, no external reference):
    assets/skills-build.svg, assets/skills-ai.svg   tool logos, two panels
    assets/loop-animated.svg, assets/loop-static.svg  the automation-loop graphic
    assets/terminal-animated.svg, assets/terminal-static.svg  the terminal session about me
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
import math
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


# ---------------------------------------------------------------- automation loop

LOOP_CX, LOOP_CY, LOOP_R = 260, 176, 118
LOOP_CYCLE = 12.0
# (chip text, icon id). The packet visits them clockwise from the top.
LOOP_NODES = [
    ("[ingest]", "in"), ("[llm]", "ai"), ("[tool_call]", "tool"),
    ("[eval]", "shield"), ("[human ok]", "eye"), ("[ship]", "up"),
]
ICON_PATHS = {
    "in": '<path d="M-5 -10 H5 V-1 H10 L0 10 L-10 -1 H-5 Z"/>',
    "ai": '<path d="M0 -11 L3 -3 L11 0 L3 3 L0 11 L-3 3 L-11 0 L-3 -3 Z"/>',
    "tool": ('<circle r="5" fill="none" stroke-width="2.4"/><path stroke-width="2.4" d="M0 -11 V-7 M0 7 V11 '
             'M-11 0 H-7 M7 0 H11 M-8 -8 L-5 -5 M5 5 L8 8 M-8 8 L-5 5 M5 -5 L8 -8"/>'),
    "shield": ('<path fill="none" stroke-width="2.4" d="M0 -11 L9 -7 V0 C9 6 4 10 0 12 C-4 10 -9 6 -9 0 V-7 Z"/>'
               '<path fill="none" stroke-width="2.4" d="M-4 1 L-1 4 L5 -3"/>'),
    "eye": '<path fill="none" stroke-width="2.4" d="M-11 0 Q0 -10 11 0 Q0 10 -11 0 Z"/><circle r="3.4"/>',
    "up": '<path d="M0 -11 L8 3 H3 V10 H-3 V3 H-8 Z"/>',
}


def build_loop(animated: bool) -> str:
    width, height = 520, 362
    node_pos = []
    for i in range(len(LOOP_NODES)):
        ang = math.radians(-90 + i * 60)
        node_pos.append((LOOP_CX + LOOP_R * math.cos(ang), LOOP_CY + LOOP_R * math.sin(ang)))
    css = ""
    if animated:
        step = LOOP_CYCLE / len(LOOP_NODES)
        rules = [
            f".orb{{transform-origin:{LOOP_CX}px {LOOP_CY}px;animation:spin {LOOP_CYCLE:g}s linear infinite}}",
            "@keyframes spin{to{transform:rotate(360deg)}}",
            f".core{{transform-origin:{LOOP_CX}px {LOOP_CY}px;animation:beat 3s ease-in-out infinite}}",
            "@keyframes beat{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}",
            f"@keyframes lit{{0%{{stroke:{GOLD};fill:#2b2a10}}16%,100%{{stroke:{LINE};fill:{TILE}}}}}",
            "@keyframes chip{0%{opacity:1}16%,100%{opacity:.55}}",
        ]
        for i in range(len(LOOP_NODES)):
            rules.append(f".n{i}{{animation:lit {LOOP_CYCLE:g}s linear infinite;animation-delay:{i * step:g}s}}"
                         f".c{i}{{animation:chip {LOOP_CYCLE:g}s linear infinite;animation-delay:{i * step:g}s}}")
        css = "".join(rules) + REDUCED
    out = svg_open(width, height, "The automation loop",
                   "A loop with six stages: ingest, language model, tool call, evaluation, human approval, ship. "
                   "A real check and a person sit between the model and the world.", css)
    out.append(f'<defs><pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">'
               f'<path d="M20 0 H0 V20" fill="none" stroke="#161b22" stroke-width="1"/></pattern>'
               f'<radialGradient id="glow"><stop offset="0" stop-color="{GOLD}" stop-opacity=".45"/>'
               f'<stop offset="1" stop-color="{GOLD}" stop-opacity="0"/></radialGradient></defs>')
    out.append(f'<rect width="{width}" height="{height}" fill="url(#grid)"/>')
    for x, y, sx, sy in ((10, 10, 1, 1), (510, 10, -1, 1), (10, 352, 1, -1), (510, 352, -1, -1)):
        out.append(f'<path d="M{x} {y + 18 * sy} V{y} H{x + 18 * sx}" fill="none" stroke="{GOLD}" stroke-width="2"/>')
    out.append(f'<circle cx="{LOOP_CX}" cy="{LOOP_CY}" r="{LOOP_R}" fill="none" stroke="{LINE}" stroke-width="2" '
               f'stroke-dasharray="2 7"/>')
    out.append(f'<circle cx="{LOOP_CX}" cy="{LOOP_CY}" r="86" fill="url(#glow)"/>')
    core_cls = ' class="core"' if animated else ""
    out.append(f'<g{core_cls}><circle cx="{LOOP_CX}" cy="{LOOP_CY}" r="50" fill="{BG}" stroke="{GOLD}" '
               f'stroke-width="2"/>'
               f'<text x="{LOOP_CX}" y="{LOOP_CY + 4}" text-anchor="middle" font-size="30" font-weight="800" '
               f'fill="{GOLD}" class="m">AI</text>'
               f'<text x="{LOOP_CX}" y="{LOOP_CY + 26}" text-anchor="middle" font-size="11" fill="{MUTED}" '
               f'class="m">+ real checks</text></g>')
    require_text_contrast(GOLD, BG, "loop core")
    require_text_contrast(MUTED, BG, "loop core caption")
    require_text_contrast(TEXT, BG, "loop chips")
    for i, ((chip, icon), (x, y)) in enumerate(zip(LOOP_NODES, node_pos)):
        ncls = f' class="n{i}"' if animated else ""
        ccls = f' class="m c{i}"' if animated else ' class="m"'
        out.append(f'<circle{ncls} cx="{x:.1f}" cy="{y:.1f}" r="26" fill="{TILE}" stroke="{LINE}" stroke-width="2"/>')
        out.append(f'<g transform="translate({x:.1f} {y:.1f}) scale(1.05)" fill="{GOLD}" stroke="{GOLD}" '
                   f'stroke-linejoin="round">{ICON_PATHS[icon]}</g>')
        if i == 0:
            tx, ty, anchor = x, y - 36, "middle"
        elif i == 3:
            tx, ty, anchor = x, y + 52, "middle"
        elif i in (1, 2):
            tx, ty, anchor = x + 36, y + 5, "start"
        else:
            tx, ty, anchor = x - 36, y + 5, "end"
        out.append(f'<text{ccls} x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anchor}" font-size="14" font-weight="700" '
                   f'fill="{TEXT}">{escape(chip)}</text>')
    if animated:
        out.append(f'<g class="orb"><circle cx="{LOOP_CX}" cy="{LOOP_CY - LOOP_R}" r="14" fill="{GOLD}" '
                   f'fill-opacity=".25"/><circle cx="{LOOP_CX}" cy="{LOOP_CY - LOOP_R}" r="6" fill="{GOLD}"/></g>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- terminal content

LOGO = [
    " ####   ####  ",
    "#    # #    # ",
    "#      #    # ",
    "#      #  # # ",
    "#    # #   ## ",
    " ####   #### #",
]
NEO_ROWS = [
    ("role", "Applied AI, Forward-Deployed"),
    ("base", "Jacksonville FL, remote"),
    ("status", "open to FDE roles"),
    ("builds", "LLM systems with real checks"),
    ("stack", "Python, FastAPI, React, Docker"),
    ("models", "LangChain, LiteLLM, OpenRouter"),
    ("rule", "a real check beats a prompt"),
    ("off duty", "books, billiards, aquariums"),
]
NEO_SWATCH = ["#7d6f17", "#a89816", "#c4b228", GOLD, "#efe9d2", "#3fb950", "#ff7b72", "#58a6ff"]


TERM_CYCLE = 30.0
CHAR_W = 8.4
HELP_LINES = [
    ("cqc: applied AI, forward-deployed engineer", TEXT),
    None,
    ("USAGE     cqc <command>", MUTED),
    ("COMMANDS", GOLD),
    ("  build    ship LLM systems with real checks", TEXT),
    ("  audit    grade an LLM stack, A to F", TEXT),
    ("  explain  write down what broke", TEXT),
    ("  hire     remote, Jacksonville FL", TEXT),
]
RUN_STEPS = [
    ("ingest", "the job someone does by hand"),
    ("llm", "drafts and dry runs, never auto-publish"),
    ("tool", "run the real check, not a guess"),
    ("eval", "score it before anyone sees it"),
    ("human", "a person approves"),
    ("ship", "then watch it after it ships"),
]
# (start, end) seconds of each act inside one cycle
ACTS = [(0.0, 9.0), (9.4, 20.0), (20.4, 28.6)]


def _pct(seconds: float) -> str:
    return f"{seconds / TERM_CYCLE * 100:.3f}"


def build_terminal(animated: bool) -> str:
    """Three acts: --help, a build run in the style of an agent CLI, then whoami --verbose.

    The static twin shows only the last act.
    """
    width, height = 520, 330
    css_rules: list[str] = []
    counter = [0]

    def appear(start: float, end: float) -> str:
        """Class name for an element visible from `start` to `end` seconds (within one cycle)."""
        n = counter[0]
        counter[0] += 1
        css_rules.append(f"@keyframes v{n}{{0%,{_pct(start)}%{{opacity:0}}{_pct(start + 0.01)}%,{_pct(end)}%{{opacity:1}}"
                         f"{_pct(end + 0.01)}%,100%{{opacity:0}}}}.v{n}{{animation:v{n} {TERM_CYCLE:g}s linear infinite}}")
        return f"v{n}"

    def typed(text: str, x: float, y: float, start: float, dur: float, end: float, fill: str) -> list[str]:
        cls = "m " + appear(start, end) if animated else "m"
        out = [f'<text class="{cls}" x="{x}" y="{y}" font-size="14" fill="{fill}" xml:space="preserve">'
               f'{escape(text)}</text>']
        if animated:
            n = counter[0]
            counter[0] += 1
            w = len(text) * CHAR_W + 8
            css_rules.append(
                f"@keyframes t{n}{{0%,{_pct(start)}%{{transform:scaleX(1);animation-timing-function:steps({len(text)},end)}}"
                f"{_pct(start + dur)}%,100%{{transform:scaleX(0)}}}}"
                f".t{n}{{transform-origin:{x + w:g}px {y}px;animation:t{n} {TERM_CYCLE:g}s linear infinite}}")
            out.append(f'<g class="{appear(start, end)}"><rect class="t{n}" x="{x - 2}" y="{y - 15}" '
                       f'width="{w:g}" height="21" fill="{TILE}"/></g>')
        return out

    def shown(start: float, end: float) -> str:
        return f' class="{appear(start, end)}"' if animated else ""

    out = svg_open(width, height, "About me, as a simulated terminal session",
                   "A simulated terminal, not a real tool or a real session. First cqc --help lists four commands: build, "
                   "audit, explain and hire. Then a run steps through ingest, llm, tool, eval, human review and ship. "
                   "Then cqc about prints: Title: Applied AI, Forward-Deployed Engineer. Base: Jacksonville, Florida, remote. Status: "
                   "open to Forward-Deployed Engineer roles. Builds LLM systems with real checks. Stack: Python, "
                   "FastAPI, React, Docker. Models: LangChain, LiteLLM, OpenRouter. Rule: a real check beats a prompt. "
                   "Off duty: books, billiards, aquariums.", "")
    out.append(f'<rect x="8" y="8" width="504" height="314" rx="12" fill="{TILE}" stroke="{LINE}"/>')
    for i, col in enumerate((RED, GOLD, GREEN)):
        out.append(f'<circle cx="{30 + i * 20}" cy="30" r="6" fill="{col}"/>')
    require_text_contrast(MUTED, TILE, "terminal window title")
    for fg in (GOLD, TEXT, GREEN, RED):
        require_text_contrast(fg, TILE, "terminal text")
    out.append(f'<text x="260" y="35" text-anchor="middle" font-size="13" fill="{MUTED}">simulated terminal (illustration)</text>')

    if animated:
        # Act 1: --help
        a0, a1 = ACTS[0]
        out += typed("$ cqc --help", 26, 66, a0 + 0.4, 1.3, a1, GOLD)
        t, y = a0 + 2.2, 94
        for line in HELP_LINES:
            if line is None:
                y += 10
                continue
            text, fill = line
            out.append(f'<text class="m {appear(t, a1)}" x="26" y="{y}" font-size="14" fill="{fill}" '
                       f'xml:space="preserve">{escape(text)}</text>')
            t += 0.55
            y += 20
        # Act 2: a build run
        b0, b1 = ACTS[1]
        out += typed("$ cqc run --with-review", 26, 66, b0 + 0.3, 1.5, b1, GOLD)
        t, y = b0 + 2.6, 98
        for name, note in RUN_STEPS:
            vis = appear(t, b1)
            out.append(f'<circle class="{vis}" cx="32" cy="{y - 4}" r="4" fill="{TEXT}"/>')
            out.append(f'<text class="m {vis}" x="46" y="{y}" font-size="14" fill="{TEXT}" font-weight="700">'
                       f'{escape(name)}</text>')
            out.append(f'<text class="m {vis}" x="112" y="{y}" font-size="14" fill="{MUTED}">{escape(note)}</text>')
            tick = appear(t + 0.7, b1)
            out.append(f'<path class="{tick}" d="M{width - 50} {y - 5} l4 4 l8 -9" fill="none" stroke="{GREEN}" '
                       f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')
            t += 1.15
            y += 26
        out.append(f'<text class="m {appear(t + 0.2, b1)}" x="46" y="{y + 6}" font-size="14" fill="{GREEN}">'
                   f'ready for review</text>')
        c0, c1 = ACTS[2]
    else:
        c0, c1 = 0.0, TERM_CYCLE

    # Act 3 (and the static twin): whoami --verbose
    out += typed("$ cqc about --verbose", 26, 66, c0 + 0.3, 1.8, c1, GOLD)
    t0 = c0 + 2.4
    for r, row in enumerate(LOGO):
        out.append(f'<text class="m{(" " + appear(t0, c1)) if animated else ""}" x="26" y="{100 + r * 17}" '
                   f'font-size="14" fill="{GOLD}" xml:space="preserve">{escape(row)}</text>')
    out.append(f'<text class="m{(" " + appear(t0 + 0.3, c1)) if animated else ""}" x="170" y="92" font-size="14" '
               f'font-weight="700" fill="{TEXT}">Christopher Queen</text>')
    out.append(f'<line{shown(t0 + 0.3, c1)} x1="170" y1="100" x2="330" y2="100" stroke="{LINE}"/>')
    for i, (k, v) in enumerate(NEO_ROWS):
        y = 124 + i * 22
        vis = f' class="{appear(t0 + 0.7 + i * 0.5, c1)}"' if animated else ""
        out.append(f'<g{vis}><text class="m" x="170" y="{y}" font-size="14" fill="{GOLD}" font-weight="700">'
                   f'{escape(k)}</text><text class="m" x="250" y="{y}" font-size="14" fill="{TEXT}">'
                   f'{escape(v)}</text></g>')
    sw_vis = f' class="{appear(t0 + 0.7 + len(NEO_ROWS) * 0.5, c1)}"' if animated else ""
    swatches = "".join(f'<rect x="{170 + i * 26}" y="{124 + len(NEO_ROWS) * 22 + 6}" width="22" height="14" rx="3" '
                       f'fill="{col}"/>' for i, col in enumerate(NEO_SWATCH))
    out.append(f"<g{sw_vis}>{swatches}</g>")
    if animated:
        # the style element was opened empty above; fill it now
        css = f"text{{font-family:{SANS}}}.m{{font-family:{MONO}}}" + "".join(css_rules) + REDUCED
        out = [line if not line.startswith("<style>") else f"<style>{css}</style>" for line in out]
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


CARD_HEIGHT = 272  # every card the same height so a pair sits level


def build_card(card: dict, icons: dict) -> str:
    width = 392
    broke_lines = card["broke"]
    height = CARD_HEIGHT
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
        out.append(icon_group(icons, slug, x, height - 44, 24, TILE))
        x += 34
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- main

def build_all() -> dict[str, str]:
    icons = load_icons()
    files = {f"{panel}.svg": build_skills(panel, icons) for panel, _, _ in SKILL_PANELS}
    files["loop-animated.svg"] = build_loop(True)
    files["loop-static.svg"] = build_loop(False)
    files["terminal-animated.svg"] = build_terminal(True)
    files["terminal-static.svg"] = build_terminal(False)
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
