"""Offline tests for scripts/make_growing_snake.py and scripts/build_assets.py."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.path.insert(0, str(ROOT / "scripts"))
    spec.loader.exec_module(mod)
    return mod


snake = load("make_growing_snake")
assets = load("build_assets")
LEVEL_NAMES = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]


def payload(weeks: int = 20, every: int = 3) -> dict:
    out, total, n = [], 0, 0
    for w in range(weeks):
        days = []
        for d in range(7):
            n += 1
            count = (n % 5) if n % every == 0 else 0
            level = min(4, count)
            total += count
            days.append({"contributionCount": count, "contributionLevel": LEVEL_NAMES[level],
                         "weekday": d, "date": "2026-01-01"})
        out.append({"contributionDays": days})
    return {"data": {"user": {"contributionsCollection": {"contributionCalendar": {
        "totalContributions": total, "weeks": out}}}}}


def cells_of(p: dict):
    return snake.parse_calendar(p)


# ------------------------------------------------------------- parsing

def test_parse_returns_cells_and_total():
    cells, total = cells_of(payload())
    assert len(cells) == 140 and total == sum(c["count"] for c in cells)


def _cal(p):
    return p["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def _day(p):
    return _cal(p)["weeks"][0]["contributionDays"][0]


@pytest.mark.parametrize("mutate", [
    lambda p: p.pop("data"),
    lambda p: p["data"]["user"].update(contributionsCollection=None),
    lambda p: _cal(p).update(weeks=[]),
    lambda p: _cal(p).update(totalContributions=-1),
    lambda p: _cal(p).update(totalContributions=10**6),
    lambda p: _day(p).update(weekday=9),
    lambda p: _day(p).update(contributionLevel="HUGE"),
    lambda p: _day(p).update(contributionCount=True),
    lambda p: _cal(p)["weeks"][0]["contributionDays"].append(dict(_day(p))),
])
def test_parse_rejects_malformed_payloads(mutate):
    p = payload()
    mutate(p)
    with pytest.raises(snake.CalendarError):
        cells_of(p)


# ------------------------------------------------------------- path and growth

def test_walk_moves_one_square_at_a_time_over_real_days_and_eats_them_all():
    cells, _ = cells_of(payload(53, 2))
    walk = snake.plan_walk(cells)
    valid = {(c["col"], c["row"]) for c in cells}
    food = {(c["col"], c["row"]) for c in cells if c["level"] > 0}
    for a, b in zip(walk.path[snake.PAD - 1:], walk.path[snake.PAD:]):
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        assert b in valid
    assert set(walk.eat_index) == food, "every active day is eaten"


def test_the_snake_never_runs_into_its_own_body():
    for weeks, every in ((20, 3), (53, 2), (53, 1)):
        cells, _ = cells_of(payload(weeks, every))
        walk = snake.plan_walk(cells)
        for k, length in enumerate(walk.lengths):
            window = walk.path[max(0, k - length + 1):k + 1]
            assert len(set(window)) == len(window), (weeks, every, k)


def test_the_walk_is_deterministic_and_wanders_rather_than_sweeping_columns():
    cells, _ = cells_of(payload(53, 3))
    first, second = snake.plan_walk(cells), snake.plan_walk(cells)
    assert first.path == second.path and first.lengths == second.lengths
    assert len(first.path) < 7 * 53 + snake.PAD, "it only goes where it needs to"


def head_track(svg: str) -> list[tuple[float, float]]:
    start = svg.index("@keyframes mv{")
    block = svg[start:svg.index("}}", start)]
    pts = re.findall(r"translate\((-?\d+(?:\.\d+)?)px,(-?\d+(?:\.\d+)?)px\)", block)
    return [(float(x), float(y)) for x, y in pts]


def segment_delays(svg: str) -> list[float]:
    found = re.findall(r"\.s(\d+)\{animation-delay:(-?\d+(?:\.\d+)?)s\}", svg)
    return [float(d) for _, d in sorted(found, key=lambda m: int(m[0]))]


def test_the_head_track_matches_the_walk_and_the_body_replays_it_with_a_lag():
    cells, total = cells_of(payload(53, 2))
    svg = snake.build_svg(cells, total, "dark", True)
    walk = snake.plan_walk(cells)
    track = head_track(svg)
    assert len(track) == len(walk.path) + 1, "one keyframe per step plus the held end"
    assert track[0][0] < 0, "the snake starts off the board"
    delays = segment_delays(svg)
    n_seg = int(round((max(walk.lengths) - 1) / snake.SEG_STEP)) + 1
    assert len(delays) == n_seg
    assert delays[0] == 0
    for j, delay in enumerate(delays):
        assert delay == pytest.approx(j * snake.SEG_STEP / walk.speed, abs=0.001)


def test_each_segment_appears_only_once_the_body_is_long_enough_to_reach_it():
    cells, total = cells_of(payload(53, 2))
    svg = snake.build_svg(cells, total, "dark", True)
    walk = snake.plan_walk(cells)
    times = []
    for j in range(int(round((max(walk.lengths) - 1) / snake.SEG_STEP)) + 1):
        m = re.search(r"@keyframes v" + str(j) + r"\{0%,(\d+(?:\.\d+)?)%\{opacity:0\}", svg)
        times.append(float(m.group(1)))
    assert times == sorted(times), "longer reach appears later"
    assert times[-1] > times[0]


def test_the_snake_uses_no_dashes_and_no_pathlength_so_safari_draws_one_snake():
    cells, total = cells_of(payload(53, 2))
    svg = snake.build_svg(cells, total, "dark", True)
    assert "pathLength" not in svg and "stroke-dash" not in svg


def test_eaten_squares_empty_when_the_head_arrives_and_refill_at_the_end():
    cells, total = cells_of(payload())
    svg = snake.build_svg(cells, total, "dark", True)
    active = [c for c in cells if c["level"] > 0]
    assert svg.count("@keyframes e") == len(active)
    empty = snake.theme_colours("dark")["levels"][0]
    pattern = (r"@keyframes e\d+\{0%,(\d+(?:\.\d+)?)%\{fill:(#\w+)\}(\d+(?:\.\d+)?)%,(\d+(?:\.\d+)?)%"
               r"\{fill:(#\w+)\}100%\{fill:(#\w+)\}\}")
    first = re.search(pattern, svg)
    assert first and first.group(5) == empty and first.group(2) == first.group(6)
    assert float(first.group(1)) < float(first.group(3)) < float(first.group(4)) < 100


def test_inactive_squares_are_not_animated():
    cells, total = cells_of(payload())
    svg = snake.build_svg(cells, total, "light", True)
    idle = sum(c["level"] == 0 for c in cells)
    assert len(re.findall(r'<rect[^>]* width="12"', svg)) == len(cells)
    assert svg.count('class="a e') == len(cells) - idle


# ------------------------------------------------------------- output safety

def test_static_twin_has_no_motion_and_animated_has_the_reduced_motion_rule():
    cells, total = cells_of(payload())
    static = snake.build_svg(cells, total, "light", False)
    animated = snake.build_svg(cells, total, "light", True)
    assert "@keyframes" not in static and "animation" not in static and "<path" not in static
    assert "@media (prefers-reduced-motion: reduce){*{animation:none!important}}" in animated


def test_freeze_override_is_only_added_on_request():
    cells, total = cells_of(payload())
    assert "animation-play-state" not in snake.build_svg(cells, total, "dark", True)
    assert "animation-play-state" in snake.build_svg(cells, total, "dark", True, freeze=3)


def run_cli(tmp_path, *args):
    script = str(ROOT / "scripts" / "make_growing_snake.py")
    return subprocess.run([sys.executable, script, *args], capture_output=True, text=True, cwd=tmp_path)


def test_cli_writes_four_files_that_pass_the_lint(tmp_path):
    fx = tmp_path / "cal.json"
    fx.write_text(json.dumps(payload(53, 2)), encoding="utf-8")
    out = tmp_path / "dist"
    res = run_cli(tmp_path, "--fixture", str(fx), "--out-dir", str(out))
    assert res.returncode == 0, res.stderr
    names = sorted(p.name for p in out.iterdir())
    assert names == ["snake-dark.svg", "snake-static-dark.svg", "snake-static-light.svg", "snake.svg"]
    lint = subprocess.run([sys.executable, str(ROOT / "scripts" / "lint_svg.py"), "--profile", "chart",
                           "--require-opaque-background", "--min-bytes", "5000", "--max-bytes", "1500000",
                           "--expect", "rect=100", *map(str, out.glob("*.svg"))], capture_output=True, text=True)
    assert lint.returncode == 0, lint.stdout + lint.stderr


def test_cli_fails_closed_and_writes_nothing_on_bad_data(tmp_path):
    fx = tmp_path / "cal.json"
    fx.write_text('{"data": null}', encoding="utf-8")
    out = tmp_path / "dist"
    res = run_cli(tmp_path, "--fixture", str(fx), "--out-dir", str(out))
    assert res.returncode == 1 and "snake:" in res.stderr
    assert not out.exists() or not list(out.iterdir())


def test_cli_without_token_or_fixture_is_a_usage_error(tmp_path):
    res = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_growing_snake.py"), "--user", "x",
                          "--out-dir", str(tmp_path / "o")], capture_output=True, text=True, cwd=tmp_path,
                         env={"PATH": "/usr/bin:/bin"})
    assert res.returncode == 2


# ------------------------------------------------------------- build_assets

def test_committed_assets_match_the_builder():
    built = assets.build_all()
    for name, text in built.items():
        path = ROOT / name if "/" in name else ROOT / "assets" / name
        assert path.read_text(encoding="utf-8") == text, name


def test_assets_have_no_external_references_or_script():
    for name, text in assets.build_all().items():
        if name.endswith(".html"):
            continue
        low = text.lower()
        assert "http" not in low.replace("http://www.w3.org/2000/svg", ""), name
        assert "<script" not in low and "<animate" not in low and "<image" not in low, name


def test_graph_data_is_consistent():
    graph = assets.load_graph()
    ids = [n["id"] for n in graph["nodes"]]
    assert len(ids) == len(set(ids)) and 12 <= len(ids) <= 24
    assert all(n["kind"] in assets.KIND_STYLE for n in graph["nodes"])
    for a, b in graph["edges"]:
        assert a in ids and b in ids and a != b
    linked = {x for e in graph["edges"] for x in e}
    assert linked == set(ids), "every node connects to something"


def test_graph_layout_is_deterministic_inside_the_frame_and_keeps_nodes_apart():
    graph = assets.load_graph()
    pos = assets.layout_graph(graph)
    assert pos == assets.layout_graph(graph)
    for x, y in pos.values():
        assert 0 < x < assets.GRAPH_W and 0 < y < assets.GRAPH_H
    pts = list(pos.values())
    for i, p in enumerate(pts):
        for q in pts[i + 1:]:
            assert ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 > 22


def test_graph_static_twin_has_no_motion_and_animated_obeys_reduced_motion():
    static = assets.build_graph_svg(False)
    assert "animation" not in static and "@keyframes" not in static
    animated = assets.build_graph_svg(True)
    assert "@media (prefers-reduced-motion: reduce){*{animation:none!important}}" in animated
    for node in assets.load_graph()["nodes"]:
        assert node["label"] in static


def test_graph_page_is_self_contained_and_has_a_text_version():
    page = assets.build_graph_page()
    assert "<script src" not in page and "http://" not in page.replace("http://www.w3.org", "")
    assert "pointerdown" in page and "Text version" in page and "prefers-reduced-motion" in page
    for node in assets.load_graph()["nodes"]:
        assert node["label"] in page


def test_terminal_static_twin_has_no_motion_and_every_row_fits():
    static = assets.build_terminal(False)
    assert "animation" not in static
    for key, value in assets.NEO_ROWS:
        assert key in static and value in static
        assert len(value) <= 32


def test_terminal_shows_the_cqc_tool_and_has_no_fake_identity():
    for animated in (True, False):
        svg = assets.build_terminal(animated)
        assert ">cqc<" in svg
        assert "christopher@" not in svg.lower() and "neofetch" not in svg.lower() and "simulated" not in svg.lower()


def test_terminal_animated_covers_do_not_leak_across_acts_and_respect_reduced_motion():
    svg = assets.build_terminal(True)
    assert "@media (prefers-reduced-motion: reduce){*{animation:none!important}}" in svg
    # every typed-text cover is wrapped in a group that is only visible during its own act
    assert svg.count('<g class="v') >= 3
    assert assets.TERM_CYCLE >= 12


def test_contrast_helper_rejects_low_contrast():
    assert assets.contrast("#ffffff", "#000000") == pytest.approx(21.0)
    with pytest.raises(SystemExit):
        assets.require_text_contrast("#777777", "#888888", "test")


def test_card_claims_stay_inside_what_the_projects_support():
    """Guard against a card drifting into a claim the projects do not support."""
    joined = " ".join(" ".join(c["stake"] + c["did"] + c["familiar"] + [c["what"]]) for c in assets.CARDS).lower()
    for banned in ("revenue", "customers", "production-grade", "profit", "betting", "traceab", "guarantee"):
        assert banned not in joined, banned
    by_id = {c["id"]: c for c in assets.CARDS}
    assert any("held out" in line for line in by_id["hearing"]["did"]), "the accuracy number keeps its caveat"
    assert any("1.2 standard errors" in line for line in by_id["panthera"]["did"])
    assert "paper" in by_id["panthera"]["tag"].lower() and "no real money" in by_id["panthera"]["what"]


def test_every_card_line_fits_and_every_card_has_the_three_blocks():
    for card in assets.CARDS:
        for key in ("stake", "did", "familiar"):
            assert card[key], (card["id"], key)
            assert all(len(line) <= 50 for line in card[key]), (card["id"], key)


def test_readme_card_alt_text_is_the_card_text():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for card in assets.CARDS:
        assert assets.card_alt(card).replace('"', "&quot;") in readme, card["id"]


def test_every_output_uses_the_dark_panel_and_carries_no_count_text():
    cells, total = cells_of(payload())
    dark_bg = snake.theme_colours("dark")["bg"]
    for name, svg in snake.build_all(cells, total).items():
        assert f'fill="{dark_bg}"/>' in svg, name
        assert "<text" not in svg and "contributions in the last year" not in svg, name
        assert f"{total} contributions" not in svg, name


