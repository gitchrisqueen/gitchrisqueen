"""Offline tests for scripts/lint_svg.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "svg"
ASSETS = ROOT / "assets"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


lint_svg = _load("lint_svg")

# fixture file -> the rule that must be reported
FAILING = {
    "fail_script.svg": "forbidden-element",
    "fail_script_uppercase.svg": "forbidden-element",
    "fail_smil_animate.svg": "forbidden-element",
    "fail_smil_animatetransform_mixedcase.svg": "forbidden-element",
    "fail_smil_set.svg": "forbidden-element",
    "fail_foreignobject.svg": "forbidden-element",
    "fail_external_href.svg": "external-href",
    "fail_external_xlink_href.svg": "external-href",
    "fail_entity_javascript.svg": "script-url",
    "fail_entity_url.svg": "external-url",
    "fail_css_external_url.svg": "external-url",
    "fail_css_import.svg": "css-import",
    "fail_on_attribute.svg": "event-handler",
    "fail_on_attribute_mixedcase.svg": "event-handler",
    "fail_missing_reduced_motion.svg": "reduced-motion",
    "fail_amplitude_wave_shape.svg": "amplitude",
    "fail_amplitude_translate_y.svg": "amplitude",
    "fail_period_too_short.svg": "period",
    "fail_period_ms.svg": "period",
    "fail_two_infinite_loops.svg": "loops",
    "fail_opacity_flash.svg": "flashing",
    "fail_text_on_moving_layer.svg": "text-moves",
    "fail_no_background.svg": "background",
    "fail_translucent_background.svg": "background",
    "fail_partial_background.svg": "background",
    "fail_banner_too_wide.svg": "banner-width",
    "fail_banner_too_short.svg": "banner-height",
    "fail_doctype_entity.svg": "doctype",
    "fail_animated-static.svg": "static-twin",
    "fail_tiny.svg": "too-small",
}


def rules(result) -> set[str]:
    return {v.split(":", 1)[0] for v in result.violations}


def test_lint_svg_every_failing_fixture_is_listed():
    on_disk = {p.name for p in FIXTURES.glob("fail_*.svg")}
    assert on_disk == set(FAILING)


@pytest.mark.parametrize("name,rule", sorted(FAILING.items()))
def test_lint_svg_failing_fixture(name, rule):
    result = lint_svg.lint_file(FIXTURES / name, require_opaque_background=True)
    assert not result.ok
    assert rule in rules(result), result.violations


@pytest.mark.parametrize("name", ["pass_header_animated.svg", "pass_header-static.svg"])
def test_lint_svg_passing_fixture(name):
    result = lint_svg.lint_file(FIXTURES / name, require_opaque_background=True)
    assert result.ok, result.violations


def test_lint_svg_passing_fixture_metrics():
    result = lint_svg.lint_file(FIXTURES / "pass_header_animated.svg")
    assert result.metrics["animated"] is True
    assert result.metrics["amplitude_px"] == pytest.approx(5.0, abs=0.01)
    assert result.metrics["period_s"] == 20
    # 6% of a 160-unit banner is 9.6, so the 8 px cap governs
    assert result.metrics["amplitude_limit_px"] == 8.0


def test_lint_svg_fraction_limit_governs_on_short_banner():
    text = (FIXTURES / "pass_header_animated.svg").read_text()
    # a 140-unit banner: 6% = 8.4, still above 8; a 120-unit one would fail height
    text = text.replace('viewBox="0 0 600 160"', 'viewBox="0 0 600 140"').replace(
        'height="160" fill', 'height="140" fill'
    )
    result = lint_svg.lint_text(text, "short.svg", require_opaque_background=True)
    assert result.ok, result.violations
    assert result.metrics["amplitude_limit_px"] == 8.0


def test_lint_svg_real_assets_pass():
    files = sorted(ASSETS.glob("*.svg"))
    names = {p.name for p in files}
    assert {
        "header-animated.svg",
        "header-static.svg",
        "footer-animated.svg",
        "footer-static.svg",
    } <= names
    for path in files:
        result = lint_svg.lint_file(path, require_opaque_background=True)
        assert result.ok, (path.name, result.violations)
        if path.name.endswith("-animated.svg"):
            m = result.metrics
            assert m["animated"] is True
            assert m["amplitude_px"] <= 8.0
            assert m["amplitude_px"] <= 0.06 * m["viewbox"][3]
            assert m["period_s"] >= 12
            assert m["viewbox"][2] <= 600 and m["viewbox"][3] >= 140
        else:
            assert result.metrics["animated"] is False


def test_lint_svg_static_twin_matches_animated_design():
    for stem in ("header", "footer"):
        anim = (ASSETS / f"{stem}-animated.svg").read_text()
        static = (ASSETS / f"{stem}-static.svg").read_text()
        assert "@keyframes" not in static and "animation" not in static
        # same drawing once the stylesheet and the layer class are removed
        start, end = anim.index("  <style>"), anim.index("</style>\n") + len("</style>\n")
        stripped = anim[:start] + anim[end:]
        assert stripped.replace('class="drift"', 'class="still"') == static


def test_lint_svg_cli_real_assets_exit_zero(capsys):
    files = [str(p) for p in sorted(ASSETS.glob("*.svg"))]
    assert lint_svg.main(files + ["--require-opaque-background"]) == 0
    assert "0 failed" in capsys.readouterr().out


def test_lint_svg_cli_failing_exit_nonzero(capsys):
    code = lint_svg.main([str(FIXTURES / "fail_script.svg"), "--require-opaque-background"])
    assert code == 1
    assert "FAIL" in capsys.readouterr().out


def test_lint_svg_missing_file(tmp_path):
    result = lint_svg.lint_file(tmp_path / "nope.svg")
    assert "missing" in rules(result)


def test_lint_svg_rejects_symlink(tmp_path):
    link = tmp_path / "link.svg"
    link.symlink_to(FIXTURES / "pass_header_animated.svg")
    assert "symlink" in rules(lint_svg.lint_file(link))


def test_lint_svg_zero_byte_file(tmp_path):
    empty = tmp_path / "empty.svg"
    empty.write_bytes(b"")
    result = lint_svg.lint_file(empty)
    assert "too-small" in rules(result)


def test_lint_svg_chart_profile_needs_no_text_or_banner_size():
    text = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 192">'
        '<rect x="0" y="0" width="880" height="192" fill="#ffffff"/>'
        + "".join(f'<rect x="{i * 16}" y="10" width="12" height="12" fill="#9c8c12"/>' for i in range(30))
        + "</svg>"
    )
    result = lint_svg.lint_text(
        text, "snake-static-light.svg", profile="chart", require_opaque_background=True, expect={"rect": 20}
    )
    assert result.ok, result.violations
    result = lint_svg.lint_text(text, "snake.svg", profile="chart", expect={"rect": 100})
    assert "expected-element" in rules(result)


def test_lint_svg_inline_style_animation_rejected():
    text = (FIXTURES / "pass_header-static.svg").read_text().replace(
        '<g class="wave"', '<g class="wave" style="animation:drift 20s linear infinite"'
    )
    assert "inline-animation" in rules(lint_svg.lint_text(text, "x.svg"))


def test_lint_svg_rotate_transform_rejected():
    text = (FIXTURES / "pass_header_animated.svg").read_text().replace(
        "translateX(-200px)", "rotate(20deg)"
    )
    assert "transform" in rules(lint_svg.lint_text(text, "x.svg"))


def test_lint_svg_whitespace_obfuscated_javascript():
    text = (FIXTURES / "pass_header-static.svg").read_text().replace(
        "</svg>", '<a href="java&#x09;script:alert(1)"><circle r="1"/></a></svg>'
    )
    result = lint_svg.lint_text(text, "x.svg")
    assert "external-href" in rules(result)


def test_lint_svg_path_points_quadratic_extent():
    pts = lint_svg.path_points("M0 100 q25 -10 50 0 t50 0")
    ys = [p[1] for p in pts]
    assert max(ys) - min(ys) == pytest.approx(10.0, abs=0.01)


def test_lint_svg_path_points_rejects_arcs():
    with pytest.raises(ValueError):
        lint_svg.path_points("M0 0 a5 5 0 0 1 10 0")
