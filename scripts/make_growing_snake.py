#!/usr/bin/env python3
"""Draw the contribution calendar as a snake that grows as it eats.

Usage:
    GITHUB_TOKEN=... python scripts/make_growing_snake.py --user NAME --out-dir dist
    python scripts/make_growing_snake.py --fixture calendar.json --out-dir dist

Writes four files: snake.svg (light, animated), snake-dark.svg (dark,
animated), snake-static-light.svg and snake-static-dark.svg (no motion).

How it works: the snake follows one fixed path, down column 1, up column 2,
and so on across the whole calendar. It eats each day that has contributions;
the day's square goes empty when the head arrives, and the snake is one square
longer from then on. All motion is CSS keyframes (no script, no SMIL). The
body is a single stroked path whose dash window (length and offset) is
animated; the dash window is `length` squares long and ends at the head.

Calendar data comes from the GitHub GraphQL API (one read-only query) or from
a fixture file with the same JSON shape. Any malformed value fails the run, so
a bad response never replaces the published files.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
GRAPHQL = "https://api.github.com/graphql"
QUERY = ("query($login:String!){user(login:$login){contributionsCollection{contributionCalendar"
         "{totalContributions weeks{contributionDays{contributionCount contributionLevel weekday date}}}}}}")
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

PITCH = 15          # distance between square centres, px
CELL = 12           # square size, px
WIDTH = 840
SPEED = 16.0        # squares per second
START_LEN = 4       # snake length before it eats anything
GROWTH = 0.3        # squares of length gained per square eaten
PAD = 3             # off-board squares the snake walks in from
HOLD = 1.0          # seconds the full snake stays after the last square
FADE = 1.0
EMPTY_HOLD = 1.5
REFILL = 1.0
MAX_WEEKS = 60
REDUCED = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"
SANS = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"


class CalendarError(Exception):
    pass


# ------------------------------------------------------------------ data

def parse_calendar(payload: object) -> tuple[list[dict], int]:
    """Return ([{col,row,count,level}], total) or raise CalendarError."""
    try:
        cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]  # type: ignore[index]
        weeks = cal["weeks"]
        total = cal["totalContributions"]
    except (KeyError, TypeError):
        raise CalendarError("response has no contribution calendar") from None
    if not isinstance(weeks, list) or not 1 <= len(weeks) <= MAX_WEEKS:
        raise CalendarError("calendar week count is out of range")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise CalendarError("calendar total is not a count")
    cells = []
    for col, week in enumerate(weeks):
        days = week.get("contributionDays") if isinstance(week, dict) else None
        if not isinstance(days, list) or not 1 <= len(days) <= 7:
            raise CalendarError("a calendar week is malformed")
        for day in days:
            if not isinstance(day, dict):
                raise CalendarError("a calendar day is malformed")
            row, count, level = day.get("weekday"), day.get("contributionCount"), day.get("contributionLevel")
            if not isinstance(row, int) or isinstance(row, bool) or not 0 <= row <= 6:
                raise CalendarError("a calendar weekday is out of range")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise CalendarError("a calendar count is invalid")
            if level not in LEVELS:
                raise CalendarError("a calendar level is unknown")
            cells.append({"col": col, "row": row, "count": count, "level": LEVELS[level]})
    if len({(c["col"], c["row"]) for c in cells}) != len(cells):
        raise CalendarError("a calendar day appears twice")
    if sum(c["count"] for c in cells) != total:
        raise CalendarError("calendar total does not match its days")
    return cells, total


def fetch_calendar(user: str, token: str) -> object:
    import update_profile as up  # reuses the redirect-refusing opener
    urllib.request.install_opener(up.make_opener())
    body = json.dumps({"query": QUERY, "variables": {"login": user}}).encode()
    req = urllib.request.Request(GRAPHQL, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
        "User-Agent": "profile-snake-generator"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.getcode() != 200 or not resp.geturl().startswith(GRAPHQL):
                raise CalendarError("unexpected response from the API")
            raw = resp.read(2_000_000)
    except urllib.error.URLError as exc:
        raise CalendarError(f"API request failed: {type(exc).__name__}") from None
    try:
        return json.loads(raw)
    except ValueError:
        raise CalendarError("API response is not JSON") from None


# ------------------------------------------------------------------ colours

def theme_colours(theme: str) -> dict:
    pairs = {p["id"]: p for p in json.loads((ROOT / "assets" / "colors.json").read_text())["pairs"]}
    levels = [pairs[f"snake-{theme}-level-{n}"]["foreground"] for n in range(5)]
    return {"levels": levels, "snake": pairs[f"snake-{theme}-snake"]["foreground"],
            "bg": pairs[f"snake-{theme}-snake"]["background"],
            "caption": pairs[f"snake-{theme}-caption"]["foreground"],
            "head": pairs[f"snake-{theme}-head"]["foreground"]}


# ------------------------------------------------------------------ geometry

def build_path(cols: int) -> list[tuple[int, int]]:
    """Grid squares in visiting order: PAD off-board squares, then every column."""
    pts = [(-PAD + i, 0) for i in range(PAD)]
    for c in range(cols):
        rows = range(7) if c % 2 == 0 else range(6, -1, -1)
        pts.extend((c, r) for r in rows)
    return pts


def fmt(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def build_svg(cells: list[dict], total: int, theme: str, animated: bool, freeze: float | None = None) -> str:
    col = theme_colours(theme)
    cols = max(c["col"] for c in cells) + 1
    board_w = cols * PITCH - (PITCH - CELL)
    left = (WIDTH - board_w) / 2
    top = 14
    height = top + 7 * PITCH - (PITCH - CELL) + 36
    path = build_path(cols)
    steps = len(path) - 1
    by_pos = {(c["col"], c["row"]): c for c in cells}
    index_of = {pos: i for i, pos in enumerate(path)}

    def centre(pos: tuple[int, int]) -> tuple[float, float]:
        return left + pos[0] * PITCH + CELL / 2, top + pos[1] * PITCH + CELL / 2

    run = steps / SPEED
    cycle = run + HOLD + FADE + EMPTY_HOLD + REFILL
    pct = lambda seconds: seconds / cycle * 100  # noqa: E731
    empty = col["levels"][0]

    css = [f"text{{font-family:{SANS}}}"]
    body = []
    eaten_idx = sorted(index_of[(c["col"], c["row"])] for c in cells if c["level"] > 0)
    desc = (f"{total} contributions in the last year, drawn as a calendar. "
            + ("A snake eats each active day and grows longer as it goes." if animated else "Static view, no motion."))
    summary = f"{total} contributions in the last year"

    # board squares
    refill_at = pct(run + HOLD + FADE + EMPTY_HOLD)
    for c in sorted(cells, key=lambda c: (c["col"], c["row"])):
        x, y = centre((c["col"], c["row"]))
        x -= CELL / 2
        y -= CELL / 2
        fill = col["levels"][c["level"]]
        cls = ""
        if animated and c["level"] > 0:
            k = index_of[(c["col"], c["row"])]
            at = pct(k / SPEED)
            css.append(f"@keyframes e{k}{{0%,{fmt(at)}%{{fill:{fill}}}{fmt(at + 0.25)}%,{fmt(refill_at)}%"
                       f"{{fill:{empty}}}100%{{fill:{fill}}}}}.e{k}{{animation-name:e{k}}}")
            cls = f' class="a e{k}"'
        body.append(f'<rect{cls} x="{fmt(x)}" y="{fmt(y)}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}"/>')

    if animated:
        css.append(f".a{{animation-duration:{fmt(cycle)}s;animation-iteration-count:infinite;"
                   f"animation-timing-function:linear}}")
        eaten_so_far = 0
        eaten_set = set(eaten_idx)
        body_frames, head_frames = [], []
        for k in range(len(path)):
            if k in eaten_set:
                eaten_so_far += 1
            length = round(START_LEN + GROWTH * eaten_so_far, 3)
            at = fmt(pct(k / SPEED))
            body_frames.append(f"{at}%{{stroke-dasharray:{length} 1000;stroke-dashoffset:{length - k}}}")
            head_frames.append(f"{at}%{{stroke-dashoffset:{1 - k}}}")
        end = fmt(pct(run))
        css.append("@keyframes sb{" + "".join(body_frames) + f"100%{{stroke-dasharray:{length} 1000;"
                   f"stroke-dashoffset:{length - steps}}}}}")
        css.append("@keyframes sh{" + "".join(head_frames) + f"100%{{stroke-dashoffset:{1 - steps}}}}}")
        fade_a, fade_b = pct(run + HOLD), pct(run + HOLD + FADE)
        css.append(f"@keyframes sg{{0%,{fmt(fade_a)}%{{opacity:1}}{fmt(fade_b)}%,99.9%{{opacity:0}}100%{{opacity:1}}}}")
        css.append(".sb{animation-name:sb}.sh{animation-name:sh}.sg{animation-name:sg}")
        css.append(REDUCED)
        if freeze is not None:
            css.append(f"*{{animation-play-state:paused!important;animation-delay:-{fmt(freeze)}s!important}}")
        d = "M" + " L".join(f"{fmt(centre(p)[0])} {fmt(centre(p)[1])}" for p in path)
        stroke = (f'fill="none" stroke-linecap="round" stroke-linejoin="round" pathLength="{steps}"')
        body.append(
            f'<g class="a sg"><path class="a sb" d="{d}" {stroke} stroke="{col["snake"]}" stroke-width="9" '
            f'stroke-dasharray="{START_LEN} 1000" stroke-dashoffset="{START_LEN}"/>'
            f'<path class="a sh" d="{d}" {stroke} stroke="{col["head"]}" stroke-width="13" '
            f'stroke-dasharray="1 1000" stroke-dashoffset="1"/></g>')

    caption_y = top + 7 * PITCH - (PITCH - CELL) + 24
    body.append(f'<text x="{fmt(left)}" y="{caption_y}" font-size="12" fill="{col["caption"]}">{summary}'
                + (". The snake grows a little with each active day it eats." if animated else ".")
                + "</text>")
    head = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" '
        f'height="{height}" role="img">',
        "<title>Contribution calendar</title>", f"<desc>{desc}</desc>",
        f"<style>{''.join(css)}</style>",
        f'<rect width="{WIDTH}" height="{height}" fill="{col["bg"]}"/>',
    ]
    return "\n".join(head + body + ["</svg>"]) + "\n"


def build_all(cells: list[dict], total: int) -> dict[str, str]:
    return {
        "snake.svg": build_svg(cells, total, "light", True),
        "snake-dark.svg": build_svg(cells, total, "dark", True),
        "snake-static-light.svg": build_svg(cells, total, "light", False),
        "snake-static-dark.svg": build_svg(cells, total, "dark", False),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--user", help="GitHub login (needs GITHUB_TOKEN)")
    ap.add_argument("--fixture", help="read the GraphQL response from this file instead of the API")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--freeze", type=float, help="preview only: write snake-freeze-<theme>.svg paused at N seconds")
    args = ap.parse_args(argv)
    try:
        if args.fixture:
            payload = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        else:
            token = os.environ.get("GITHUB_TOKEN", "")
            if not args.user or not token:
                print("need --user and GITHUB_TOKEN, or --fixture", file=sys.stderr)
                return 2
            payload = fetch_calendar(args.user, token)
        cells, total = parse_calendar(payload)
    except (CalendarError, OSError, ValueError) as exc:
        print(f"snake: {exc}", file=sys.stderr)
        return 1
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = build_all(cells, total)
    if args.freeze is not None:
        files = {f"snake-freeze-{t}.svg": build_svg(cells, total, t, True, args.freeze) for t in ("light", "dark")}
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
        print(f"wrote {out / name} ({len(text)} bytes)")
    print(f"snake: {len(cells)} days, {total} contributions, {sum(c['level'] > 0 for c in cells)} eaten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
