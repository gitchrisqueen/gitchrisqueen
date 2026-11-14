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

def test_path_visits_every_square_once_and_each_step_is_one_square():
    path = snake.build_path(20)
    assert len(path) == snake.PAD + 140 and len(set(path)) == len(path)
    for (c1, r1), (c2, r2) in zip(path, path[1:]):
        assert abs(c1 - c2) + abs(r1 - r2) == 1


def keyframes(svg: str, name: str) -> list[tuple[float, float, float]]:
    start = svg.index("@keyframes " + name + "{")
    block = svg[start:svg.index("}}", start)]
    out = []
    frame = r"(\d{1,3}(?:\.\d+)?)%\{stroke-dasharray:(\d+(?:\.\d+)?) 1000;stroke-dashoffset:(-?\d+(?:\.\d+)?)\}"
    for m in re.finditer(frame, block):
        out.append((float(m.group(1)), float(m.group(2)), float(m.group(3))))
    return out


def test_snake_gets_longer_only_when_it_eats_and_never_shrinks():
    cells, total = cells_of(payload())
    svg = snake.build_svg(cells, total, "dark", True)
    frames = keyframes(svg, "sb")
    lengths = [f[1] for f in frames]
    assert lengths[0] == snake.START_LEN
    assert all(b >= a for a, b in zip(lengths, lengths[1:]))
    eaten = sum(c["level"] > 0 for c in cells)
    assert lengths[-1] == pytest.approx(snake.START_LEN + snake.GROWTH * eaten, abs=0.01)
    assert lengths[-1] > lengths[0] + 5, "the snake visibly grows"


def test_head_stays_at_the_front_of_the_body():
    cells, total = cells_of(payload())
    svg = snake.build_svg(cells, total, "dark", True)
    body = keyframes(svg, "sb")
    for i, (_, length, offset) in enumerate(body[:-1]):
        # dash covers path positions [-offset, length - offset]; its end is the head at index i
        assert length - offset == pytest.approx(i, abs=0.01)


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
        assert (ROOT / "assets" / name).read_text(encoding="utf-8") == text, name


def test_assets_have_no_external_references_or_script():
    for name, text in assets.build_all().items():
        low = text.lower()
        assert "http" not in low.replace("http://www.w3.org/2000/svg", ""), name
        assert "<script" not in low and "<animate" not in low and "<image" not in low, name


def test_loop_static_twin_has_no_motion_and_shows_every_stage():
    static = assets.build_loop(False)
    assert "animation" not in static and "@keyframes" not in static
    for chip, _ in assets.LOOP_NODES:
        assert chip in static


def test_loop_animated_has_reduced_motion_rule_and_bounded_motion():
    animated = assets.build_loop(True)
    assert "@media (prefers-reduced-motion: reduce){*{animation:none!important}}" in animated
    assert assets.LOOP_CYCLE >= 6
    assert "visibility" not in animated and "display:none" not in animated


def test_terminal_static_twin_has_no_motion_and_every_row_fits():
    static = assets.build_terminal(False)
    assert "animation" not in static
    for key, value in assets.NEO_ROWS:
        assert key in static and value in static
        assert len(value) <= 32


def test_terminal_is_labelled_simulated_and_has_no_fake_identity():
    for animated in (True, False):
        svg = assets.build_terminal(animated)
        assert "simulated terminal" in svg
        assert "christopher@" not in svg.lower() and "neofetch" not in svg.lower()


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


def test_card_claims_are_the_short_forms_of_the_readme_claims():
    """Guard against a card drifting into a claim the README does not make."""
    joined = " ".join(" ".join(c["lines"] + c["broke"]) for c in assets.CARDS).lower()
    for banned in ("roi of", "%", "revenue", "customers", "production-grade"):
        assert banned not in joined


def test_every_output_uses_the_dark_panel_and_carries_no_count_text():
    cells, total = cells_of(payload())
    dark_bg = snake.theme_colours("dark")["bg"]
    for name, svg in snake.build_all(cells, total).items():
        assert f'fill="{dark_bg}"/>' in svg, name
        assert "<text" not in svg and "contributions in the last year" not in svg, name
        assert f"{total} contributions" not in svg, name


def test_snake_body_is_thinner_than_a_square():
    cells, total = cells_of(payload())
    svg = snake.build_svg(cells, total, "dark", True)
    width = float(re.search(r'class="a sb"[^>]*stroke-width="([\d.]+)"', svg).group(1))
    assert width <= snake.CELL * 0.65


def test_card_and_skills_images_stay_narrow_enough_for_a_phone():
    for name, text in assets.build_all().items():
        if name.startswith("header-") or name.startswith("footer-"):
            continue
        width = int(re.search(r'viewBox="0 0 (\d+) ', text).group(1))
        assert width <= 520, f"{name} is {width} wide"


def test_terminal_sample_report_is_labelled_synthetic_and_tools_match_the_skills_list():
    svg = assets.build_terminal(True)
    assert "synthetic data" in svg and "sample output, not a real audit" in svg
    for name, _ in assets.TOOLS:
        assert name in svg
    assert len(assets.TOOLS) == 6 and all(g in "ABC" for _, g, _ in assets.AUDIT_ROWS)
