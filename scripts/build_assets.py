#!/usr/bin/env python3
"""Build the profile's hand-designed SVG assets from data files.

Usage:
    python scripts/build_assets.py            # write assets/*.svg
    python scripts/build_assets.py --check    # exit 1 if a committed file differs

Outputs (all opaque-background, no script, no external reference):
    assets/skills-build.svg, assets/skills-ai.svg   tool logos, two panels
    assets/graph-animated.svg, assets/graph-static.svg  the knowledge-graph graphic
    docs/graph/index.html                              its interactive, draggable version
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
import random
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


SIZE_BOOST = {"mysql": 1.3}  # a few marks sit small in their 24-unit box


def icon_group(icons: dict, slug: str, x: float, y: float, size: float, bg: str) -> str:
    icon = icons[slug]
    colour = glyph_colour(slug, icon["hex"], bg)
    boost = SIZE_BOOST.get(slug, 1.0)
    x -= size * (boost - 1) / 2
    y -= size * (boost - 1) / 2
    size *= boost
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


# ---------------------------------------------------------------- knowledge graph

KIND_STYLE = {
    # kind: (radius, fill, label size, bold). Tools are drawn as logo discs and carry no label.
    "me": (18, GOLD, 17, True),
    "project": (13, "#c4b228", 16, True),
    "offer": (13, "#efe9d2", 16, True),
    "practice": (11, GREEN, 16, True),
    "tech": (15, TILE, 0, False),
}
TECH_ICON = {
    "python": "python", "fastapi": "fastapi", "redis": "redis", "react": "react", "selenium": "selenium",
    "langchain": "langchain", "docker": "docker", "actions": "githubactions", "node": "nodedotjs",
}
GRAPH_W, GRAPH_H = 520, 430


def load_graph() -> dict:
    return json.loads((ROOT / "data" / "graph.json").read_text(encoding="utf-8"))


def layout_graph(graph: dict, width: int = GRAPH_W, height: int = GRAPH_H) -> dict[str, tuple[float, float]]:
    """The tidiest of 40 seeded force layouts: fewest overlapping labels. Deterministic, so the SVG needs no script."""
    nodes = {n["id"]: n for n in graph["nodes"]}

    def boxes(pos: dict) -> list[tuple[float, float, float, float]]:
        out = []
        for nid, (x, y) in pos.items():
            r, _, size, _ = KIND_STYLE[nodes[nid]["kind"]]
            w = len(nodes[nid]["label"]) * size * 0.6 if size else 0
            out.append((x - max(w / 2, r), y - r, x + max(w / 2, r), y + r + (size + 4 if size else 0)))
        return out

    def overlaps(pos: dict) -> float:
        bs, total = boxes(pos), 0.0
        for i, a in enumerate(bs):
            if a[0] < 6 or a[2] > width - 6 or a[1] < 6 or a[3] > height - 6:
                total += 80
            for b in bs[i + 1:]:
                dx = min(a[2], b[2]) - max(a[0], b[0])
                dy = min(a[3], b[3]) - max(a[1], b[1])
                if dx > 0 and dy > 0:
                    total += dx * dy
        return total

    best = min((_layout_once(graph, width, height, seed) for seed in range(60)), key=overlaps)
    return best


def _layout_once(graph: dict, width: int, height: int, seed: int) -> dict[str, tuple[float, float]]:
    rnd = random.Random(seed)
    ids = [n["id"] for n in graph["nodes"]]
    pos = {i: [width / 2 + rnd.uniform(-90, 90), height / 2 + rnd.uniform(-70, 70)] for i in ids}
    pos["me"] = [width / 2, height / 2]
    k = math.sqrt(width * height / len(ids)) * 0.78
    nodes_by_id = {n["id"]: n for n in graph["nodes"]}

    def bounds(nid: str) -> tuple[float, float, float, float]:
        r, _, size, _ = KIND_STYLE[nodes_by_id[nid]["kind"]]
        half = max(r, len(nodes_by_id[nid]["label"]) * size * 0.3) + 8 if size else r + 8
        return half, width - half, r + 8, height - (r + (size + 6 if size else 0) + 8)
    for it in range(500):
        temp = 24 * (1 - it / 500) + 0.6
        disp = {i: [0.0, 0.0] for i in ids}
        for x, i in enumerate(ids):
            for j in ids[x + 1:]:
                dx, dy = pos[i][0] - pos[j][0], pos[i][1] - pos[j][1]
                d = math.hypot(dx, dy) or 0.01
                f = k * k / d
                disp[i][0] += dx / d * f
                disp[i][1] += dy / d * f
                disp[j][0] -= dx / d * f
                disp[j][1] -= dy / d * f
        for a_, b_ in graph["edges"]:
            dx, dy = pos[a_][0] - pos[b_][0], pos[a_][1] - pos[b_][1]
            d = math.hypot(dx, dy) or 0.01
            f = d * d / k
            for node, sign in ((a_, -1), (b_, 1)):
                disp[node][0] += sign * dx / d * f
                disp[node][1] += sign * dy / d * f
        for i in ids:
            disp[i][0] += (width / 2 - pos[i][0]) * 0.9
            disp[i][1] += (height / 2 - pos[i][1]) * 0.9
            d = math.hypot(*disp[i]) or 0.01
            step = min(d, temp)
            x0, x1, y0, y1 = bounds(i)
            pos[i][0] = min(x1, max(x0, pos[i][0] + disp[i][0] / d * step))
            pos[i][1] = min(y1, max(y0, pos[i][1] + disp[i][1] / d * step))
    return {i: (round(v[0], 1), round(v[1], 1)) for i, v in pos.items()}


def build_graph_svg(animated: bool) -> str:
    graph = load_graph()
    pos = layout_graph(graph)
    nodes = {n["id"]: n for n in graph["nodes"]}
    width, height = GRAPH_W, GRAPH_H
    css = ""
    if animated:
        rules = [
            "@keyframes f0{0%{transform:translate(0,0)}100%{transform:translate(4px,-3px)}}",
            "@keyframes f1{0%{transform:translate(0,0)}100%{transform:translate(-4px,3px)}}",
            "@keyframes f2{0%{transform:translate(0,0)}100%{transform:translate(3px,4px)}}",
            "@keyframes f3{0%{transform:translate(0,0)}100%{transform:translate(-3px,-4px)}}",
            "@keyframes flow{to{stroke-dashoffset:-28}}",
            ".fl{animation:flow 5s linear infinite}",
        ]
        for n, nid in enumerate(nodes):
            rules.append(f".n{n}{{animation:f{n % 4} {7 + (n * 5) % 6}s ease-in-out infinite alternate;"
                         f"animation-delay:-{(n * 3) % 7}s}}")
        css = "".join(rules) + REDUCED
    names = ", ".join(n["label"] + (" (an offer, no engagement delivered yet)" if n["kind"] == "offer" else "")
                      for n in graph["nodes"])
    out = svg_open(width, height, "What I work with, as a knowledge graph",
                   "A graph of how my projects, practices and tools connect. Nodes: " + names + ". "
                   "Open the interactive version to drag the nodes.", css)
    for x, y, sx, sy in ((10, 10, 1, 1), (510, 10, -1, 1), (10, 420, 1, -1), (510, 420, -1, -1)):
        out.append(f'<path d="M{x} {y + 16 * sy} V{y} H{x + 16 * sx}" fill="none" stroke="{GOLD}" stroke-width="2"/>')
    flow_kinds = {"practice", "offer"}
    for a_, b_ in graph["edges"]:
        (x1, y1), (x2, y2) = pos[a_], pos[b_]
        out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#3b434d" stroke-width="1.4"/>')
        if animated and (nodes[a_]["kind"] in flow_kinds or nodes[b_]["kind"] in flow_kinds):
            out.append(f'<line class="fl" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{GOLD}" stroke-width="1.8" '
                       f'stroke-linecap="round" stroke-dasharray="1 13"/>')
    icons = load_icons()
    for n, node in enumerate(graph["nodes"]):
        r, fill, size, bold = KIND_STYLE[node["kind"]]
        x, y = pos[node["id"]]
        cls = f' class="n{n}"' if animated else ""
        require_text_contrast(TEXT, BG, "graph label")
        if node["kind"] == "tech":
            stroke = LINE
            body = f'<circle cx="{x}" cy="{y}" r="{r}" fill="{TILE}" stroke="{stroke}" stroke-width="2"/>'
            slug = TECH_ICON.get(node["id"])
            if slug:
                body += icon_group(icons, slug, x - 9, y - 9, 18, TILE)
            else:
                body += (f'<rect x="{x - 9}" y="{y - 9}" width="18" height="18" rx="4" fill="{GOLD}"/>'
                         f'<path d="M{x + 1.5} {y - 7} L{x - 4.5} {y + 1} H{x - 0.5} L{x - 1.5} {y + 7} '
                         f'L{x + 4.5} {y - 1.5} H{x + 0.5} Z" fill="{BG}"/>')
            out.append(f"<g{cls}>{body}</g>")
            continue
        out.append(f'<g{cls}><circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{BG}" stroke-width="2"/>'
                   f'<text x="{x}" y="{y + r + size + 1}" text-anchor="middle" font-size="{size}" '
                   f'font-weight="{700 if bold else 400}" fill="{TEXT}" paint-order="stroke" stroke="{BG}" '
                   f'stroke-width="4">{escape(node["label"])}</text></g>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


GRAPH_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>What Christopher Queen works with</title>
<meta name="description" content="An interactive knowledge graph of the projects, practices and tools Christopher Queen works with. Drag the nodes.">
<style>
:root{--bg:#0d1117;--tile:#161b22;--line:#30363d;--gold:#e9d437;--text:#e6edf3;--muted:#9ba7b4}
*{box-sizing:border-box}html,body{height:100%;margin:0;background:var(--bg);color:var(--text);
font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;overflow:hidden}
canvas{display:block;width:100%;height:100%;touch-action:none;cursor:grab}
canvas.over{cursor:pointer}canvas.drag{cursor:grabbing}
header{position:fixed;left:16px;top:12px;right:16px;display:flex;justify-content:space-between;gap:12px;pointer-events:none}
header h1{margin:0;font-size:15px;font-weight:700;color:var(--gold)}header p{margin:2px 0 0;font-size:12px;color:var(--muted)}
header a{pointer-events:auto;color:var(--gold);font-size:13px;text-decoration:none;border:1px solid var(--line);
border-radius:8px;padding:6px 10px;background:var(--tile);white-space:nowrap;align-self:flex-start}
#card{position:fixed;left:12px;right:12px;bottom:12px;max-width:520px;background:var(--tile);border:1px solid var(--line);
border-radius:12px;padding:12px 14px;font-size:14px;line-height:1.4}
#card b{color:var(--gold)}#card small{display:block;color:var(--muted);margin-top:6px}
#legend{position:fixed;right:12px;bottom:12px;font-size:12px;color:var(--muted);display:flex;flex-direction:column;gap:4px}
#legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
details{position:fixed;left:12px;top:56px;max-width:min(520px,calc(100% - 24px));font-size:13px}
details summary{color:var(--muted);cursor:pointer}
details ul{margin:6px 0 0;padding:10px 14px 10px 28px;background:var(--tile);border:1px solid var(--line);border-radius:10px;
max-height:50vh;overflow:auto}
@media (max-width:640px){#legend{display:none}}
</style>
</head>
<body>
<canvas id="g" role="img" aria-label="Knowledge graph of the projects, practices and tools I work with. A text list of the same connections is under the Text version control."></canvas>
<header><div><h1>What I work with</h1><p>Drag a node. Tap or hover to see how it ties in.</p></div>
<a href="https://github.com/gitchrisqueen">Back to the profile</a></header>
<details><summary>Text version</summary><ul id="list"></ul></details>
<div id="card"><b>Christopher</b><br>Applied AI / Forward-Deployed Engineer. Builds LLM systems with real checks around the model.<small>Pull a node to see the web move.</small></div>
<div id="legend"></div>
<script>
const DATA = __DATA__;
const COLORS = {me:'#e9d437',project:'#c4b228',offer:'#efe9d2',practice:'#3fb950',tech:'#58a6ff'};
const RADIUS = {me:17,project:12,offer:12,practice:10,tech:7};
const LABEL = {me:'700 15px',project:'700 13px',offer:'700 13px',practice:'700 12.5px',tech:'400 11.5px'};
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const cv = document.getElementById('g'), ctx = cv.getContext('2d');
const card = document.getElementById('card');
let W = 0, H = 0, dpr = 1;
const idx = {}; DATA.nodes.forEach((n, i) => idx[n.id] = i);
const nodes = DATA.nodes.map((n, i) => ({...n, r: RADIUS[n.kind], x: 0, y: 0, vx: 0, vy: 0, deg: 0, nb: new Set()}));
const links = DATA.edges.map(([a, b]) => ({a: idx[a], b: idx[b]}));
links.forEach(l => {nodes[l.a].deg++; nodes[l.b].deg++; nodes[l.a].nb.add(l.b); nodes[l.b].nb.add(l.a);});
function connected(n) { return [...n.nb].map(i => nodes[i].label); }
function describe(n) {
  const names = connected(n).join(', ');
  const note = n.note || ('Used in: ' + names + '.');
  return '<b>' + n.label + '</b><br>' + note + (n.note ? '<small>Connected to: ' + names + '.</small>' : '');
}
const list = document.getElementById('list');
nodes.forEach(n => {const li = document.createElement('li'); li.textContent = n.label + ' (' + n.kind + '): ' + (n.note ? n.note + ' ' : '') + 'Connected to ' + connected(n).join(', ') + '.'; list.appendChild(li);});
const legend = document.getElementById('legend');
[['me','me'],['project','projects'],['offer','offer'],['practice','practices'],['tech','tools']].forEach(([k, t]) => {
  const d = document.createElement('div'); d.innerHTML = '<i style="background:' + COLORS[k] + '"></i>' + t; legend.appendChild(d);});
function resize() {
  dpr = Math.min(2, devicePixelRatio || 1); W = innerWidth; H = innerHeight;
  cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  if (!nodes[0].x) nodes.forEach((n, i) => {const a = i / nodes.length * 6.283; n.x = W / 2 + Math.cos(a) * Math.min(W, H) * 0.3; n.y = H / 2 + Math.sin(a) * Math.min(W, H) * 0.3;});
}
addEventListener('resize', () => {resize(); draw();}); resize();
let alpha = 1, hover = -1, sel = -1, dragging = -1, moved = 0, running = false;
function step() {
  const L = Math.max(80, Math.min(W, H) * 0.2), cx = W / 2, cy = H / 2 + 20;
  for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
    const a = nodes[i], b = nodes[j]; let dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy + 0.01; const d = Math.sqrt(d2);
    const f = (L * L * 1.7) / d2 * alpha; dx /= d; dy /= d;
    a.vx += dx * f; a.vy += dy * f; b.vx -= dx * f; b.vy -= dy * f;
  }
  for (const l of links) {
    const a = nodes[l.a], b = nodes[l.b]; const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 0.01;
    const f = (d - L) * 0.045 * alpha; a.vx += dx / d * f; a.vy += dy / d * f; b.vx -= dx / d * f; b.vy -= dy / d * f;
  }
  nodes.forEach((n, i) => {
    n.vx += (cx - n.x) * 0.004 * alpha; n.vy += (cy - n.y) * 0.004 * alpha;
    if (i === dragging) {n.vx = n.vy = 0; return;}
    n.vx *= 0.82; n.vy *= 0.82; n.x += n.vx; n.y += n.vy;
    n.x = Math.max(n.r + 8, Math.min(W - n.r - 8, n.x)); n.y = Math.max(n.r + 64, Math.min(H - n.r - card.offsetHeight - 30, n.y));
  });
}
function draw() {
  ctx.clearRect(0, 0, W, H);
  const focus = hover >= 0 ? hover : (dragging >= 0 ? dragging : sel);
  const near = focus >= 0 ? nodes[focus].nb : new Set();
  for (const l of links) {
    const on = focus >= 0 && (l.a === focus || l.b === focus);
    ctx.strokeStyle = on ? '#e9d437' : (focus >= 0 ? '#232a33' : '#3b434d'); ctx.lineWidth = on ? 2 : 1.2;
    ctx.beginPath(); ctx.moveTo(nodes[l.a].x, nodes[l.a].y); ctx.lineTo(nodes[l.b].x, nodes[l.b].y); ctx.stroke();
  }
  nodes.forEach((n, i) => {
    const lit = focus < 0 || i === focus || near.has(i);
    ctx.globalAlpha = lit ? 1 : 0.28;
    ctx.fillStyle = COLORS[n.kind]; ctx.strokeStyle = '#0d1117'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(n.x, n.y, n.r + (i === focus ? 3 : 0), 0, 6.283); ctx.fill(); ctx.stroke();
    ctx.font = LABEL[n.kind] + ' -apple-system, Segoe UI, Helvetica, Arial, sans-serif'; ctx.textAlign = 'center';
    ctx.lineWidth = 3; ctx.strokeStyle = '#0d1117'; ctx.fillStyle = '#e6edf3';
    ctx.strokeText(n.label, n.x, n.y + n.r + 15); ctx.fillText(n.label, n.x, n.y + n.r + 15);
  });
  ctx.globalAlpha = 1;
}
function loop() {
  running = true; step(); draw();
  alpha = Math.max(alpha * 0.985, dragging >= 0 ? 0.35 : (reduce ? 0 : 0.03));
  if (alpha > 0.002 || dragging >= 0) requestAnimationFrame(loop); else running = false;
}
function kick(a) {alpha = Math.max(alpha, a); if (!running) loop();}
if (reduce) {for (let i = 0; i < 400; i++) step(); draw();} else loop();
function pick(x, y) {let best = -1, bd = 1e9; nodes.forEach((n, i) => {const d = Math.hypot(n.x - x, n.y - y); if (d < n.r + 12 && d < bd) {bd = d; best = i;}}); return best;}
function pt(e) {const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top];}
cv.addEventListener('pointerdown', e => {
  const [x, y] = pt(e), i = pick(x, y); if (i < 0) return;
  dragging = i; moved = 0; cv.setPointerCapture(e.pointerId); cv.classList.add('drag'); kick(0.6);
});
cv.addEventListener('pointermove', e => {
  const [x, y] = pt(e);
  if (dragging >= 0) {nodes[dragging].x = x; nodes[dragging].y = y; moved++; kick(0.5); return;}
  const i = pick(x, y); if (i !== hover) {hover = i; cv.classList.toggle('over', i >= 0); card.innerHTML = describe(nodes[i >= 0 ? i : (sel >= 0 ? sel : 0)]); draw();}
});
function release(e) {
  if (dragging < 0) return;
  if (moved < 4) {sel = (sel === dragging) ? -1 : dragging; card.innerHTML = describe(nodes[sel >= 0 ? sel : 0]);}
  dragging = -1; cv.classList.remove('drag'); draw();
}
cv.addEventListener('pointerup', release); cv.addEventListener('pointercancel', release);
cv.addEventListener('pointerleave', () => {if (dragging < 0 && hover >= 0) {hover = -1; cv.classList.remove('over'); card.innerHTML = describe(nodes[sel >= 0 ? sel : 0]); draw();}});
card.innerHTML = describe(nodes[0]);
</script>
</body>
</html>
"""


def build_graph_page() -> str:
    graph = load_graph()
    data = json.dumps(graph, separators=(",", ":")).replace("</", "<\\/")
    return GRAPH_PAGE.replace("__DATA__", data)


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
    ("role", "Applied AI / FDE"),
    ("base", "Jacksonville FL, remote"),
    ("status", "open to FDE roles"),
    ("builds", "LLM systems, real checks"),
    ("stack", "Python, FastAPI, React"),
    ("models", "LangChain, LiteLLM"),
    ("rule", "checks beat prompts"),
    ("off duty", "billiards, books, fish"),
]
NEO_SWATCH = ["#7d6f17", "#a89816", "#c4b228", GOLD, "#efe9d2", "#3fb950", "#ff7b72", "#58a6ff"]


TERM_CYCLE = 39.0
CHAR_W = 9.6
HELP_LINES = [
    ("cqc: applied AI, forward-deployed engineer", TEXT),
    None,
    ("USAGE     cqc <command>", MUTED),
    ("COMMANDS", GOLD),
    ("  mcp      connect my skills as tools", TEXT),
    ("  call     run one skill, read its report", TEXT),
    ("  about    who I am", TEXT),
    ("  hire     remote, Jacksonville FL", TEXT),
]
# The skills, each one backed by a project on the page.
TOOLS = [
    ("llm_audit", "grade an LLM stack, A to F"),
    ("real_check", "a real check, not a guess"),
    ("drift_watch", "live vs released mismatch"),
    ("browser_flow", "web automation, dry-run modes"),
    ("ci_pipeline", "Actions that fail closed"),
    ("human_gate", "drafts; a person publishes"),
]
# Synthetic sample, labelled as such in the image: (area, grade, filled bars of 5).
AUDIT_ROWS = [
    ("spend efficiency", "B", 4),
    ("reliability", "C", 3),
    ("observability", "B", 4),
    ("governance", "C", 3),
    ("leverage", "A", 5),
]
GRADE_FILL = {"A": GREEN, "B": GOLD, "C": RED}
# (start, end) seconds of each act inside one cycle
ACTS = [(0.0, 8.0), (8.4, 18.8), (19.2, 29.0), (29.4, 37.4)]


def _pct(seconds: float) -> str:
    return f"{seconds / TERM_CYCLE * 100:.3f}"


def build_terminal(animated: bool) -> str:
    """Four acts: --help, an MCP connection that lists my skills as tools, one tool call with a synthetic sample report, then about.  # preflight: ok

    The static twin shows only the last act.
    """
    width, height = 520, 366
    css_rules: list[str] = []
    counter = [0]

    def appear(start: float, end: float) -> str:
        """Class name for an element visible from `start` to `end` seconds (within one cycle)."""
        n = counter[0]
        counter[0] += 1
        css_rules.append(f"@keyframes v{n}{{0%,{_pct(start)}%{{opacity:0}}{_pct(start + 0.01)}%,{_pct(end)}%{{opacity:1}}"  # preflight: ok
                         f"{_pct(end + 0.01)}%,100%{{opacity:0}}}}.v{n}{{animation:v{n} {TERM_CYCLE:g}s linear infinite}}")  # preflight: ok
        return f"v{n}"

    def typed(text: str, x: float, y: float, start: float, dur: float, end: float, fill: str) -> list[str]:
        cls = "m " + appear(start, end) if animated else "m"
        out = [f'<text class="{cls}" x="{x}" y="{y}" font-size="16" fill="{fill}" xml:space="preserve">'
               f'{escape(text)}</text>']
        if animated:
            n = counter[0]
            counter[0] += 1
            w = len(text) * CHAR_W + 8
            css_rules.append(
                f"@keyframes t{n}{{0%,{_pct(start)}%{{transform:scaleX(1);animation-timing-function:steps({len(text)},end)}}"  # preflight: ok
                f"{_pct(start + dur)}%,100%{{transform:scaleX(0)}}}}"
                f".t{n}{{transform-origin:{x + w:g}px {y}px;animation:t{n} {TERM_CYCLE:g}s linear infinite}}")
            out.append(f'<g class="{appear(start, end)}"><rect class="t{n}" x="{x - 2}" y="{y - 15}" '
                       f'width="{w:g}" height="21" fill="{TILE}"/></g>')
        return out

    def shown(start: float, end: float) -> str:
        return f' class="{appear(start, end)}"' if animated else ""

    out = svg_open(width, height, "About me, as a simulated terminal session",
                   "A simulated terminal, not a real tool or a real session. First cqc --help lists four commands. Then it "  # preflight: ok
                   "connects my skills over MCP and lists six tools: llm_audit, real_check, drift_watch, browser_flow, "
                   "ci_pipeline and human_gate. Then it calls llm_audit on synthetic sample data and prints sample "
                   "grades. Then cqc about prints: Title: Applied AI, Forward-Deployed Engineer. Base: Jacksonville, Florida, remote. Status: "  # preflight: ok
                   "open to Forward-Deployed Engineer roles. Builds LLM systems with real checks. Stack: Python, "
                   "FastAPI, React, Docker. Models: LangChain, LiteLLM, OpenRouter. Rule: a real check beats a prompt. "
                   "Off duty: books, billiards, aquariums.", "")
    out.append(f'<rect x="8" y="8" width="504" height="350" rx="12" fill="{TILE}" stroke="{LINE}"/>')
    for i, col in enumerate((RED, GOLD, GREEN)):
        out.append(f'<circle cx="{30 + i * 20}" cy="30" r="6" fill="{col}"/>')
    require_text_contrast(MUTED, TILE, "terminal window title")
    for fg in (GOLD, TEXT, GREEN, RED):
        require_text_contrast(fg, TILE, "terminal text")
    out.append(f'<text x="260" y="35" text-anchor="middle" font-size="16" fill="{MUTED}">simulated terminal (illustration)</text>')  # preflight: ok

    if animated:
        # Act 1: --help
        a0, a1 = ACTS[0]
        out += typed("$ cqc --help", 26, 66, a0 + 0.4, 1.0, a1, GOLD)
        t, y = a0 + 1.8, 94
        for line in HELP_LINES:
            if line is None:
                y += 10
                continue
            text, fill = line
            out.append(f'<text class="m {appear(t, a1)}" x="26" y="{y}" font-size="16" fill="{fill}" '
                       f'xml:space="preserve">{escape(text)}</text>')
            t += 0.4
            y += 22
        # Act 2: connect over MCP, list the tools
        b0, b1 = ACTS[1]
        out += typed("$ cqc mcp connect skills", 26, 66, b0 + 0.3, 1.5, b1, GOLD)
        t = b0 + 2.2
        vis = appear(t, b1)
        out.append(f'<circle class="{vis}" cx="32" cy="90" r="4" fill="{TEXT}"/>')
        out.append(f'<text class="m {vis}" x="46" y="94" font-size="16" fill="{TEXT}">connecting to my skills over MCP</text>')  # preflight: ok
        out.append(f'<path class="{appear(t + 0.8, b1)}" d="M{width - 50} 89 l4 4 l8 -9" fill="none" stroke="{GREEN}" '
                   f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')
        out.append(f'<text class="m {appear(t + 1.6, b1)}" x="46" y="120" font-size="16" fill="{MUTED}">'
                   f'connected (simulated). {len(TOOLS)} tools found:</text>')
        t, y = t + 2.4, 148
        for name, note in TOOLS:
            vis = appear(t, b1)
            out.append(f'<text class="m {vis}" x="46" y="{y}" font-size="16" fill="{GOLD}" font-weight="700">'
                       f'{escape(name)}</text>')
            out.append(f'<text class="m {vis}" x="186" y="{y}" font-size="16" fill="{TEXT}">{escape(note)}</text>')
            t += 0.55
            y += 26
        # Act 3: call one tool, read the report (synthetic sample)
        c0_, c1_ = ACTS[2]
        out += typed("$ cqc call llm_audit --sample", 26, 66, c0_ + 0.3, 1.7, c1_, GOLD)
        t = c0_ + 2.4
        vis = appear(t, c1_)
        out.append(f'<circle class="{vis}" cx="32" cy="90" r="4" fill="{TEXT}"/>')
        out.append(f'<text class="m {vis}" x="46" y="94" font-size="16" fill="{TEXT}">llm_audit: read-only, synthetic data</text>')  # preflight: ok
        t, y = t + 1.0, 126
        for area, grade, bars in AUDIT_ROWS:
            vis = appear(t, c1_)
            out.append(f'<text class="m {vis}" x="46" y="{y}" font-size="16" fill="{TEXT}">{escape(area)}</text>')
            out.append(f'<text class="m {vis}" x="214" y="{y}" font-size="16" font-weight="700" '
                       f'fill="{GRADE_FILL[grade]}">{grade}</text>')
            for k in range(5):
                fill = GRADE_FILL[grade] if k < bars else LINE
                out.append(f'<rect class="{vis}" x="{244 + k * 20}" y="{y - 11}" width="16" height="12" rx="2" '
                           f'fill="{fill}"/>')
            t += 0.55
            y += 26
        vis = appear(t + 0.4, c1_)
        out.append(f'<text class="m {vis}" x="46" y="{y + 8}" font-size="16" fill="{GOLD}">next: put a real check behind the model</text>')  # preflight: ok
        out.append(f'<text class="m {appear(t + 1.2, c1_)}" x="46" y="{y + 32}" font-size="16" fill="{MUTED}">'
                   f'sample output, not a real audit</text>')
        c0, c1 = ACTS[3]
    else:
        c0, c1 = 0.0, TERM_CYCLE

    # Act 3 (and the static twin): whoami --verbose
    out += typed("$ cqc about --verbose", 26, 66, c0 + 0.3, 1.8, c1, GOLD)
    t0 = c0 + 2.4
    for r, row in enumerate(LOGO):
        out.append(f'<text class="m{(" " + appear(t0, c1)) if animated else ""}" x="26" y="{100 + r * 17}" '
                   f'font-size="16" fill="{GOLD}" xml:space="preserve">{escape(row)}</text>')
    out.append(f'<text class="m{(" " + appear(t0 + 0.3, c1)) if animated else ""}" x="176" y="92" font-size="16" '
               f'font-weight="700" fill="{TEXT}">Christopher Queen</text>')
    out.append(f'<line{shown(t0 + 0.3, c1)} x1="176" y1="102" x2="420" y2="102" stroke="{LINE}"/>')
    for i, (k, v) in enumerate(NEO_ROWS):
        y = 128 + i * 24
        vis = f' class="{appear(t0 + 0.7 + i * 0.5, c1)}"' if animated else ""
        out.append(f'<g{vis}><text class="m" x="176" y="{y}" font-size="16" fill="{GOLD}" font-weight="700">'
                   f'{escape(k)}</text><text class="m" x="272" y="{y}" font-size="16" fill="{TEXT}">'
                   f'{escape(v)}</text></g>')
    sw_vis = f' class="{appear(t0 + 0.7 + len(NEO_ROWS) * 0.5, c1)}"' if animated else ""
    swatches = "".join(f'<rect x="{176 + i * 28}" y="{128 + len(NEO_ROWS) * 24 + 4}" width="24" height="14" rx="3" '
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
        "what": "A LinkedIn content and engagement app.",
        "stake": ["The live app sat on an old release for a", "day, and nobody told."],
        "did": ["Safe database changes ship on their own;", "risky ones hold and alert me. Of 134 past", "changes, 102 would ship on their own."],
        "familiar": ["Has a release sat unshipped because a", "gate held it and no one told you?"],
        "icons": ["fastapi", "celery", "redis", "mysql", "react", "docker"],
        "built": "FastAPI, Celery, Redis, MySQL, React and Docker",
    },
    {
        "id": "cpcc", "tag": "Instructor admin tool", "title": "CPCC Task Automation",
        "what": "Grading and admin tool for my own courses.",
        "stake": ["One false \"does not compile\" verdict floored", "a submission's whole grade."],
        "did": ["A real compiler now overrules the model.", "\"Can't verify\" never counts as a fail; the", "compile check never runs student code."],
        "familiar": ["Does an AI verdict in your workflow ever count", "with no hard check behind it?"],
        "icons": ["python", "streamlit", "selenium", "langchain"],
        "built": "Python, Streamlit, Selenium and LangChain",
    },
    {
        "id": "hearing", "tag": "Speaker identification", "title": "hearing-copilot",
        "what": "Names the speakers in a hearing transcript.",
        "stake": ["A wrong speaker name pins words on the", "wrong person."],
        "did": ["Scored 91 min of real court audio first:", "99.2% right on the 89.8% it auto-accepted.", "One hearing, not held out, no interval."],
        "familiar": ["Does your AI guess who said what, with", "nobody checking the guesses?"],
        "icons": ["javascript", "nodedotjs"],
        "built": "JavaScript and Node.js",
    },
    {
        "id": "panthera", "tag": "Prediction pipeline, paper only", "title": "panthera",
        "what": "An MLB prediction pipeline, no real money.",
        "stake": ["Scheduled runs produced no picks for 14", "slate days, and every run showed green."],
        "did": ["Fixed the cause; a daily health check now", "flags a no-picks slate about a day later.", "I also won't call +7.99% an edge: it is", "about 1.2 standard errors from zero."],
        "familiar": ["Do your scheduled jobs ever run green for", "weeks while quietly producing nothing?"],
        "icons": ["python", "githubactions"],
        "built": "Python and GitHub Actions",
    },
]
CARD_BLOCKS = (("At stake", "stake"), ("What I did", "did"), ("Sound familiar?", "familiar"))


def card_alt(card: dict) -> str:
    return (f'{card["title"]}. {card["what"]} At stake: {" ".join(card["stake"])} What I did: {" ".join(card["did"])} '
            f'Sound familiar? {" ".join(card["familiar"])} Built with {card["built"]}.')


def _card_height() -> int:
    most = max(sum(24 + 19 * len(c[key]) + 8 for _, key in CARD_BLOCKS) for c in CARDS)
    return 110 + most + 44


CARD_HEIGHT = _card_height()  # every card the same height so a pair sits level


def build_card(card: dict, icons: dict) -> str:
    width, height = 392, CARD_HEIGHT
    out = svg_open(width, height, card["title"], card_alt(card))
    out.append(f'<defs><clipPath id="r"><rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="12"/>'
               f'</clipPath></defs>')
    out.append(f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="12" fill="{TILE}" stroke="{LINE}"/>')
    out.append(f'<rect x="1" y="1" width="6" height="{height - 2}" fill="{GOLD}" clip-path="url(#r)"/>')
    for fg, where in ((GOLD, "card tag"), (TEXT, "card title"), (MUTED, "card body")):
        require_text_contrast(fg, TILE, where)
    out.append(f'<text x="26" y="34" font-size="13" fill="{GOLD}">{escape(card["tag"])}</text>')
    out.append(f'<text x="26" y="64" font-size="22" font-weight="700" fill="{TEXT}">{escape(card["title"])}</text>')
    out.append(f'<text x="26" y="88" font-size="13.5" fill="{MUTED}">{escape(card["what"])}</text>')
    y = 118
    for label, key in CARD_BLOCKS:
        out.append(f'<text x="26" y="{y}" font-size="13" font-weight="700" fill="{GOLD}">{escape(label)}</text>')
        y += 20
        for line in card[key]:
            out.append(f'<text x="26" y="{y}" font-size="13.5" fill="{TEXT}">{escape(line)}</text>')
            y += 19
        y += 12
    x = 26
    for slug in card["icons"]:
        out.append(icon_group(icons, slug, x, height - 44, 24, TILE))
        x += 34
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- click-to-open pills

PILLS = [
    ("pill-merged", "$ git log --merged upstream", "Merged pull requests in other people's projects (select to open)"),
    ("pill-hire", "$ sudo hire-me", "Hire me, or book the audit (select to open)"),
    ("pill-status", "$ cat live-status", "Live status of the four checks (select to open)"),
]


def build_pill(pill_id: str) -> str:
    _, cmd, alt = next(p for p in PILLS if p[0] == pill_id)
    width, height = 520, 46
    out = svg_open(width, height, alt, alt)
    require_text_contrast(GOLD, TILE, "pill command")
    require_text_contrast(MUTED, TILE, "pill hint")
    out.append(f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="10" fill="{TILE}" stroke="{GOLD}" '
               f'stroke-width="1.5"/>')
    out.append(f'<text class="m" x="18" y="29" font-size="16" fill="{GOLD}">{escape(cmd)}</text>')
    out.append(f'<text x="{width - 18}" y="29" text-anchor="end" font-size="17" fill="{MUTED}">select to open</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- main

def build_all() -> dict[str, str]:
    icons = load_icons()
    files = {f"{panel}.svg": build_skills(panel, icons) for panel, _, _ in SKILL_PANELS}
    files["graph-animated.svg"] = build_graph_svg(True)
    files["graph-static.svg"] = build_graph_svg(False)
    files["terminal-animated.svg"] = build_terminal(True)
    files["terminal-static.svg"] = build_terminal(False)
    for card in CARDS:
        files[f"card-{card['id']}.svg"] = build_card(card, icons)
    for pill_id, _, _ in PILLS:
        files[f"{pill_id}.svg"] = build_pill(pill_id)
    files["docs/graph/index.html"] = build_graph_page()  # a key with a slash is relative to the repo root
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
        path = (ROOT / name) if "/" in name else (out_dir / name)
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
