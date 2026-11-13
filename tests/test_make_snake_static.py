"""Offline tests for scripts/make_snake_static.py (no network, no GitHub)."""

from __future__ import annotations

import importlib.util
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "make_snake_static.py"
LINT = ROOT / "scripts" / "lint_svg.py"

spec = importlib.util.spec_from_file_location("make_snake_static", SCRIPT)
mss = importlib.util.module_from_spec(spec)
sys.modules["make_snake_static"] = mss
spec.loader.exec_module(mss)


def snk_svg(cells: int = 371, *, fills: bool = True, style: bool = True) -> str:
    """Build an SVG shaped like the snake generator's svg-only output."""
    css = (
        ":root{--cb:#1b1f230a;--cs:purple;--ce:#ebedf0;--c0:#ebedf0;--c1:#9be9a8;--c2:#40c463}"
        ".c{shape-rendering:geometricPrecision;fill:var(--ce);stroke-width:1px;"
        "stroke:var(--cb);animation:none 75300ms linear infinite;width:12px;height:12px}"
    )
    for i in range(0, cells, 5):  # every fifth cell is a contribution day
        css += (
            f"@keyframes c{i}{{{(i % 90) + 1}.12%{{fill:var(--c1)}}"
            f"{(i % 90) + 1}.14%,100%{{fill:var(--ce)}}}}"
            f".c.c{i}{{fill:var(--c2);animation-name:c{i}}}"
        )
    css += (
        ".u{transform-origin:0 0;transform:scale(0,1);animation:none linear 75300ms infinite}"
        ".s{shape-rendering:geometricPrecision;fill:var(--cs);animation:none linear 75300ms infinite}"
        "@keyframes s0{0%,99.87%{transform:translate(0px,-16px)}0.13%{transform:translate(0px,0px)}}"
        ".s.s0{transform:translate(0px,-16px);animation-name:s0}"
        "@-webkit-keyframes legacy{0%{opacity:0}100%{opacity:1}}"
    )
    if not fills:
        css = ".c{width:12px;height:12px}.s{width:1px}"
    rects = "".join(
        f'<rect class="c c{i}" x="{2 + 16 * (i // 7)}" y="{2 + 16 * (i % 7)}" rx="2" ry="2"/>'
        for i in range(cells)
    )
    body = (
        ("<style>" + css + "</style>" if style else "")
        + rects
        + '<rect class="s s0" x="0.8" y="0.8" width="14.4" height="14.4" rx="4.5" ry="4.5"/>'
    )
    return (
        '<svg viewBox="-16 -32 880 192" width="880" height="192" '
        'xmlns="http://www.w3.org/2000/svg"><desc>Generated for tests</desc>' + body + "</svg>"
    )


# ------------------------------------------------------------------ static twin


def test_keyframes_and_animation_removed():
    out = mss.make_static(snk_svg(), "#ffffff")
    assert "@keyframes" not in out.lower()
    assert "-webkit-keyframes" not in out.lower()
    assert "animation" not in out.lower()
    assert mss.static_problems(out) == []


def test_fills_and_other_declarations_survive():
    out = mss.make_static(snk_svg(), "#ffffff")
    assert ".c.c0{fill:var(--c2)}" in out  # non-default cell fill
    assert ".c.c5{fill:var(--c2)}" in out
    assert "fill:var(--cs)" in out  # snake fill
    assert "fill:var(--ce)" in out  # base cell fill
    assert "stroke:var(--cb)" in out
    assert ":root{--cb:#1b1f230a;--cs:purple;" in out  # custom properties kept
    assert ".s.s0{transform:translate(0px,-16px)}" in out  # snake parked at its start
    assert ".u{transform-origin:0 0;transform:scale(0,1)}" in out


def test_background_rect_is_first_child_and_full_size():
    out = mss.make_static(snk_svg(), "#FFF")
    root = ET.fromstring(out)
    first = list(root)[0]
    assert first.tag.endswith("rect")
    assert first.get("fill") == "#ffffff"
    assert (first.get("x"), first.get("y")) == ("-16", "-32")
    assert (first.get("width"), first.get("height")) == ("880", "192")


def test_background_from_width_height_when_no_viewbox():
    svg = snk_svg().replace('viewBox="-16 -32 880 192" ', "")
    out = mss.make_static(svg, "#0d1117")
    first = list(ET.fromstring(out))[0]
    assert (first.get("x"), first.get("width"), first.get("fill")) == ("0", "880", "#0d1117")


def test_background_is_not_duplicated_when_run_twice():
    once = mss.make_static(snk_svg(), "#ffffff")
    twice = mss.inject_background(once, "#0d1117")
    assert twice.count('id="snake-bg"') == 1
    assert 'fill="#0d1117"' in twice


def test_output_is_deterministic():
    assert mss.make_static(snk_svg(), "#ffffff") == mss.make_static(snk_svg(), "#ffffff")


def test_stripped_styles_fixture_fails_validation():
    # Same cells and snake, but the style block lost every fill rule.
    stripped = snk_svg(fills=False)
    out = mss.make_static(stripped, "#ffffff")
    problems = mss.static_problems(out)
    assert any("non-default calendar cell fill" in p for p in problems)
    assert any("snake fill" in p for p in problems)


def test_missing_style_block_is_refused():
    with pytest.raises(mss.StaticTwinError):
        mss.make_static(snk_svg(style=False), "#ffffff")


def test_too_few_cells_fails_validation():
    out = mss.make_static(snk_svg(cells=10), "#ffffff")
    assert any("calendar cells" in p for p in mss.static_problems(out))


def test_leftover_animation_is_detected():
    out = mss.make_static(snk_svg(), "#ffffff").replace("</style>", ".x{animation:a 1s}</style>")
    assert "animation declaration still present" in mss.static_problems(out)


def test_smil_element_is_detected():
    out = mss.make_static(snk_svg(), "#ffffff").replace("</svg>", "<animate/></svg>")
    assert "SMIL animation element still present" in mss.static_problems(out)


def test_css_scanner_keeps_strings_and_nested_media():
    css = (
        '.a{content:"a;b{c}";animation:x 1s;fill:red}'
        "@media (min-width:1px){.b{animation-name:y;fill:blue}.c{animation:none}}"
    )
    out = mss.strip_css_animation(css)
    assert out == '.a{content:"a;b{c}";fill:red}@media (min-width:1px){.b{fill:blue}}'


def test_doctype_and_entities_rejected():
    bad = '<!DOCTYPE svg [<!ENTITY x "y">]>' + snk_svg()
    with pytest.raises(mss.StaticTwinError):
        mss.make_static(bad, "#ffffff")


def test_malformed_xml_rejected():
    with pytest.raises(mss.StaticTwinError):
        mss.make_static("<svg><style>.c{fill:red}</style>", "#ffffff")


@pytest.mark.parametrize("bad", ["white", "#12", "#gggggg", "url(#x)", "#ffffff;x"])
def test_bad_background_colour_rejected(bad):
    with pytest.raises(mss.StaticTwinError):
        mss.make_static(snk_svg(), bad)


# --------------------------------------------------------------- animated copy


def test_keep_animation_adds_background_and_motion_rule():
    out = mss.make_animated(snk_svg(), "#0d1117")
    assert "@keyframes c0" in out
    assert out.count("prefers-reduced-motion: reduce") == 1
    assert "*{animation:none!important}" in out
    assert mss.animated_problems(out) == []
    assert list(ET.fromstring(out))[0].get("fill") == "#0d1117"


def test_keep_animation_does_not_repeat_motion_rule():
    once = mss.make_animated(snk_svg(), "#0d1117")
    twice = mss.make_animated(once, "#0d1117")
    assert twice.count("prefers-reduced-motion") == 1


# ------------------------------------------------------------------------- CLI


def run_cli(tmp_path, svg, *extra):
    src, dst = tmp_path / "in.svg", tmp_path / "out.svg"
    src.write_text(svg, encoding="utf-8")
    rc = mss.main([str(src), str(dst), *extra])
    return rc, dst


def test_cli_writes_static_twin(tmp_path, capsys):
    rc, dst = run_cli(tmp_path, snk_svg(), "--bg", "#ffffff", "--no-lint")
    assert rc == 0
    assert "@keyframes" not in dst.read_text(encoding="utf-8")
    assert "wrote static" in capsys.readouterr().out


def test_cli_stripped_styles_fixture_exits_non_zero_and_writes_nothing(tmp_path, capsys):
    rc, dst = run_cli(tmp_path, snk_svg(fills=False), "--bg", "#ffffff", "--no-lint")
    assert rc == 1
    assert not dst.exists()
    assert not list(tmp_path.glob("*.partial.svg"))
    assert "make_snake_static:" in capsys.readouterr().err


def test_cli_keep_animation(tmp_path):
    rc, dst = run_cli(tmp_path, snk_svg(), "--bg", "#0d1117", "--keep-animation", "--no-lint")
    assert rc == 0
    assert "@keyframes c0" in dst.read_text(encoding="utf-8")


def test_cli_refuses_missing_input_and_same_file(tmp_path):
    assert mss.main([str(tmp_path / "nope.svg"), str(tmp_path / "o.svg"), "--bg", "#fff"]) == 1
    f = tmp_path / "same.svg"
    f.write_text(snk_svg(), encoding="utf-8")
    assert mss.main([str(f), str(f), "--bg", "#fff", "--no-lint"]) == 1


def test_cli_refuses_symlink_input(tmp_path):
    real = tmp_path / "real.svg"
    real.write_text(snk_svg(), encoding="utf-8")
    link = tmp_path / "link.svg"
    link.symlink_to(real)
    assert mss.main([str(link), str(tmp_path / "o.svg"), "--bg", "#fff", "--no-lint"]) == 1


def test_cli_requires_bg():
    with pytest.raises(SystemExit) as exc:
        mss.main(["a.svg", "b.svg"])
    assert exc.value.code == 2


def test_cli_missing_lint_script_fails_closed(tmp_path):
    rc, dst = run_cli(
        tmp_path, snk_svg(), "--bg", "#ffffff", "--lint-script", str(tmp_path / "missing.py")
    )
    assert rc == 1 and not dst.exists()


def test_cli_failing_lint_script_blocks_output(tmp_path):
    fake = tmp_path / "fake_lint.py"
    fake.write_text("import sys\nprint('FAIL')\nsys.exit(1)\n", encoding="utf-8")
    rc, dst = run_cli(tmp_path, snk_svg(), "--bg", "#ffffff", "--lint-script", str(fake))
    assert rc == 1 and not dst.exists()


def test_cli_passing_lint_script_allows_output(tmp_path):
    fake = tmp_path / "ok_lint.py"
    fake.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    rc, dst = run_cli(tmp_path, snk_svg(), "--bg", "#ffffff", "--lint-script", str(fake))
    assert rc == 0 and dst.exists()


def test_lint_is_called_with_chart_profile(tmp_path):
    fake = tmp_path / "args_lint.py"
    log = tmp_path / "args.txt"
    fake.write_text(
        f"import sys\nopen({str(log)!r}, 'w').write(' '.join(sys.argv[1:]))\n", encoding="utf-8"
    )
    rc, _ = run_cli(tmp_path, snk_svg(), "--bg", "#ffffff", "--lint-script", str(fake))
    assert rc == 0
    args = log.read_text(encoding="utf-8")
    assert "--profile chart" in args and "--require-opaque-background" in args


@pytest.mark.skipif(not LINT.is_file(), reason="scripts/lint_svg.py not present yet")
def test_real_lint_accepts_both_outputs(tmp_path):
    rc, static = run_cli(tmp_path, snk_svg(), "--bg", "#ffffff")
    assert rc == 0
    src = tmp_path / "in2.svg"
    src.write_text(snk_svg(), encoding="utf-8")
    anim = tmp_path / "anim.svg"
    assert mss.main([str(src), str(anim), "--bg", "#0d1117", "--keep-animation"]) == 0
    assert re.search(r"<rect id=\"snake-bg\"", anim.read_text(encoding="utf-8"))
