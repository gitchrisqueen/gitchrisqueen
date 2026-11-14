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
from collections import deque
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
START_LEN = 4       # snake length before it eats anything
GAP = 100000        # dash gap in px, longer than the whole path, so exactly one snake is ever drawn
HEAD_DASH = 1       # px, the head is a round-capped dot
GROWTH = 0.15       # squares of length gained per square eaten
PAD = START_LEN     # off-board squares the snake walks in from
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


# ------------------------------------------------------------------ the walk

DIRS = ((1, 0), (0, 1), (0, -1), (-1, 0))   # right, down, up, left: a fixed order keeps the walk deterministic
MAX_STEPS = 3000
CANDIDATES = 8       # nearest uneaten days tried before giving up on a safe route
MAX_PANIC = 60       # steps in a row spent only looking for room before the walk ends
RUN_TARGET = 32.0    # seconds the whole walk should take
MIN_SPEED, MAX_SPEED = 10.0, 30.0


class Walk:
    """Where the head goes, how long the body is at each step, and when each day is eaten."""

    def __init__(self, path: list[tuple[int, int]], lengths: list[int], eat_index: dict[tuple[int, int], int]):
        self.path, self.lengths, self.eat_index = path, lengths, eat_index
        steps = max(len(path) - 1, 1)
        self.speed = min(MAX_SPEED, max(MIN_SPEED, steps / RUN_TARGET))  # squares per second


def _body_length(eaten: int) -> int:
    return START_LEN + int(GROWTH * eaten)


def _advance(body: list, cell: tuple[int, int], food: set, eaten: int) -> tuple[list, int, bool]:
    """Move the head onto `cell`. Returns (new body, eaten count, legal). The body is tail first, head last."""
    new = body + [cell]
    if cell in food:
        eaten += 1
    new = new[-_body_length(eaten):] if len(new) > _body_length(eaten) else new
    return new, eaten, new.count(cell) == 1


def _room(body: list, valid: set) -> int:
    """How many free squares the head can still reach."""
    blocked = set(body[:-1]) | {body[-1]}
    seen, queue = {body[-1]}, deque([body[-1]])
    while queue:
        cx, cy = queue.popleft()
        for dx, dy in DIRS:
            n = (cx + dx, cy + dy)
            if n in valid and n not in blocked and n not in seen:
                seen.add(n)
                queue.append(n)
    return len(seen) - 1


def _routes(body: list, food: set, valid: set, eaten: int) -> list[list[tuple[int, int]]]:
    """Shortest routes to the nearest uneaten days, treating each body square as free once the tail has left it."""
    head = body[-1]
    at_cap = len(body) >= _body_length(eaten)
    free_at = {cell: (j + 1 if at_cap else 10 ** 9) for j, cell in enumerate(body)}
    dist, prev, found = {head: 0}, {}, []
    queue = deque([head])
    while queue:
        cur = queue.popleft()
        for dx, dy in DIRS:
            n = (cur[0] + dx, cur[1] + dy)
            if n not in valid or n in dist or free_at.get(n, 0) > dist[cur] + 1:
                continue
            dist[n], prev[n] = dist[cur] + 1, cur
            queue.append(n)
            if n in food:
                found.append(n)
    found.sort(key=lambda c: (dist[c], c[0], c[1]))
    routes = []
    for target in found[:CANDIDATES]:
        route, node = [], target
        while node != head:
            route.append(node)
            node = prev[node]
        routes.append(route[::-1])
    return routes


def plan_walk(cells: list[dict]) -> Walk:
    """A snake that heads for the nearest uneaten day, may double back, and never runs into its own body."""
    valid = {(c["col"], c["row"]) for c in cells}
    food = {(c["col"], c["row"]) for c in cells if c["level"] > 0}
    path = [(-PAD + i, 0) for i in range(PAD)]
    body = list(path)
    lengths = list(range(1, PAD + 1))
    eaten, eat_index, panic = 0, {}, 0

    def step(cell: tuple[int, int]) -> bool:
        nonlocal body, eaten
        new, count, legal = _advance(body, cell, food, eaten)
        if not legal:
            return False
        if cell in food:
            food.discard(cell)
            eat_index[cell] = len(path)
        body, eaten = new, count
        path.append(cell)
        lengths.append(len(body))
        return True

    while food and len(path) < MAX_STEPS:
        chosen = None
        for route in _routes(body, food, valid, eaten):
            trial, count, ok = list(body), eaten, True
            left = set(food)
            for cell in route:
                trial, count, legal = _advance(trial, cell, left, count)
                left.discard(cell)
                ok = ok and legal
            if ok and (not left or _room(trial, valid) >= len(trial)):
                chosen = route
                break
        if chosen:
            panic = 0
            for cell in chosen:
                if not step(cell):
                    break
            continue
        # no safe route to a day: take the step that leaves the most room
        head = body[-1]
        options = []
        for dx, dy in DIRS:
            n = (head[0] + dx, head[1] + dy)
            if n in valid:
                new, _, legal = _advance(body, n, food, eaten)
                if legal:
                    options.append((_room(new, valid), n))
        panic += 1
        if not options or panic > MAX_PANIC:
            break
        step(max(options, key=lambda o: o[0])[1])
    return Walk(path, lengths, eat_index)


def fmt(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def build_svg(cells: list[dict], total: int, theme: str, animated: bool, freeze: float | None = None) -> str:
    col = theme_colours(theme)
    cols = max(c["col"] for c in cells) + 1
    board_w = cols * PITCH - (PITCH - CELL)
    left = (WIDTH - board_w) / 2
    top = 14
    height = top + 7 * PITCH - (PITCH - CELL) + 14
    walk = plan_walk(cells)
    path, steps, speed = walk.path, len(walk.path) - 1, walk.speed

    def centre(pos: tuple[int, int]) -> tuple[float, float]:
        return left + pos[0] * PITCH + CELL / 2, top + pos[1] * PITCH + CELL / 2

    run = steps / speed
    cycle = run + HOLD + FADE + EMPTY_HOLD + REFILL
    pct = lambda seconds: seconds / cycle * 100  # noqa: E731
    empty = col["levels"][0]

    css = [f"text{{font-family:{SANS}}}"]
    body = []
    desc = ("Contribution calendar for the last year. "
            + ("A snake wanders over the calendar, eats each active day and grows longer as it goes."
               if animated else "Static view, no motion."))

    # board squares
    refill_at = pct(run + HOLD + FADE + EMPTY_HOLD)
    for c in sorted(cells, key=lambda c: (c["col"], c["row"])):
        x, y = centre((c["col"], c["row"]))
        x -= CELL / 2
        y -= CELL / 2
        fill = col["levels"][c["level"]]
        cls = ""
        k = walk.eat_index.get((c["col"], c["row"]))
        if animated and k is not None:
            at = pct(k / speed)
            css.append(f"@keyframes e{k}{{0%,{fmt(at)}%{{fill:{fill}}}{fmt(at + 0.25)}%,{fmt(refill_at)}%"
                       f"{{fill:{empty}}}100%{{fill:{fill}}}}}.e{k}{{animation-name:e{k}}}")
            cls = f' class="a e{k}"'
        body.append(f'<rect{cls} x="{fmt(x)}" y="{fmt(y)}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}"/>')

    if animated:
        css.append(f".a{{animation-duration:{fmt(cycle)}s;animation-iteration-count:infinite;"
                   f"animation-timing-function:linear}}")
        body_frames, head_frames = [], []
        for k, cells_long in enumerate(walk.lengths):
            at = fmt(pct(k / speed))
            dash = max(cells_long - 1, 0.01) * PITCH       # the body spans (length - 1) steps behind the head
            body_frames.append(f"{at}%{{stroke-dasharray:{fmt(dash)} {GAP};stroke-dashoffset:{fmt(dash - k * PITCH)}}}")
            head_frames.append(f"{at}%{{stroke-dashoffset:{fmt(HEAD_DASH - k * PITCH)}}}")
        last_dash = max(walk.lengths[-1] - 1, 0.01) * PITCH
        css.append("@keyframes sb{" + "".join(body_frames) + f"100%{{stroke-dasharray:{fmt(last_dash)} {GAP};"
                   f"stroke-dashoffset:{fmt(last_dash - steps * PITCH)}}}}}")
        css.append("@keyframes sh{" + "".join(head_frames) + f"100%{{stroke-dashoffset:{fmt(HEAD_DASH - steps * PITCH)}}}}}")
        fade_a, fade_b = pct(run + HOLD), pct(run + HOLD + FADE)
        css.append(f"@keyframes sg{{0%,{fmt(fade_a)}%{{opacity:1}}{fmt(fade_b)}%,99.9%{{opacity:0}}100%{{opacity:1}}}}")
        css.append(".sb{animation-name:sb}.sh{animation-name:sh}.sg{animation-name:sg}")
        css.append(REDUCED)
        if freeze is not None:
            css.append(f"*{{animation-play-state:paused!important;animation-delay:-{fmt(freeze)}s!important}}")
        d = "M" + " L".join(f"{fmt(centre(p)[0])} {fmt(centre(p)[1])}" for p in path)
        stroke = 'fill="none" stroke-linecap="round" stroke-linejoin="round"'
        body.append(
            f'<g class="a sg"><path class="a sb" d="{d}" {stroke} stroke="{col["snake"]}" stroke-width="7" '
            f'stroke-dasharray="0.01 {GAP}" stroke-dashoffset="0.01"/>'
            f'<path class="a sh" d="{d}" {stroke} stroke="{col["head"]}" stroke-width="10" '
            f'stroke-dasharray="{HEAD_DASH} {GAP}" stroke-dashoffset="{HEAD_DASH}"/></g>')

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
    # Both themes use the dark panel, so the gold levels and the cream snake read on any page theme.
    return {
        "snake.svg": build_svg(cells, total, "dark", True),
        "snake-dark.svg": build_svg(cells, total, "dark", True),
        "snake-static-light.svg": build_svg(cells, total, "dark", False),
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
