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
    "fail_css_backslash_escape.svg": "css-escape",
    "fail_css_image_set.svg": "css-forbidden",
    "fail_css_font_face.svg": "css-forbidden",
    "fail_pi_stylesheet_before.svg": "processing-instruction",
    "fail_pi_stylesheet_after.svg": "processing-instruction",
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
        banner = path.name.startswith(("header-", "footer-"))
        kwargs = {} if banner else {"profile": "chart"}
        result = lint_svg.lint_file(path, require_opaque_background=True, **kwargs)
        assert result.ok, (path.name, result.violations)
        if banner and path.name.endswith("-animated.svg"):
            m = result.metrics
            assert m["animated"] is True
            assert m["amplitude_px"] <= 8.0
            assert m["amplitude_px"] <= 0.06 * m["viewbox"][3]
            assert m["period_s"] >= 12
            assert m["viewbox"][2] <= 600 and m["viewbox"][3] >= 140
        else:
            assert result.metrics["animated"] is path.name.endswith("-animated.svg")


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
    files = [str(p) for p in sorted(ASSETS.glob("*.svg")) if p.name.startswith(("header-", "footer-"))]
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


# --------------------------------------------------------------------------
# CSS hazards: backslashes and external-loading substrings

STATIC = (FIXTURES / "pass_header-static.svg").read_text()


def _with_style_element(css: str) -> str:
    end = STATIC.index(">") + 1
    return STATIC[:end] + f"<style>{css}</style>" + STATIC[end:]


def test_lint_svg_css_font_face_fixture_reports_all_three_hazards():
    result = lint_svg.lint_file(FIXTURES / "fail_css_font_face.svg", require_opaque_background=True)
    joined = " ".join(result.violations)
    assert "backslash" in joined and "'://'" in joined and "'@font-face'" in joined


@pytest.mark.parametrize(
    "css,needle",
    [
        ('text{background:image-set("a.png" 1x)}', "image-set("),
        ('text{background:-webkit-image-set("a.png" 1x)}', "image-set("),
        ('text{background:IMAGE-SET("a.png" 1x)}', "image-set("),
        ("text{background:image-set /**/ ('a.png' 1x)}", "image-set("),
        ("text{background:image/**/('a.png')}", "image("),
        ("text{content:src('a')}", "src("),
        ("text{background:cross-fade(#a, #b)}", "cross-fade("),
        ("@media screen{@FONT-FACE{font-family:x}}", "@font-face"),
        ("text{fill:&#117;rl(#a) ;background:x}/* ok */ a{b:c://d}", "://"),
        ("text{fill:u&#92;72l(#a)}", None),
        ("text{fill:u\\72l(#a)}", None),
    ],
)
def test_lint_svg_style_element_hazards_rejected(css, needle):
    result = lint_svg.lint_text(_with_style_element(css), "x.svg")
    got = rules(result)
    assert got & {"css-forbidden", "css-escape"}, result.violations
    if needle is not None:
        assert any(needle in v for v in result.violations), result.violations


def test_lint_svg_hazard_hidden_by_comment_split_is_still_found():
    # a comment inside the token is stripped before the substring test
    result = lint_svg.lint_text(_with_style_element("text{background:image-/**/set('a' 1x)}"), "x.svg")
    assert "css-forbidden" in rules(result)


def test_lint_svg_style_attribute_hazards_rejected():
    text = STATIC.replace('<text x="40" y="80"', '<text x="40" y="80" style="background:image-set(a 1x)"', 1)
    assert "css-forbidden" in rules(lint_svg.lint_text(text, "x.svg"))
    text = STATIC.replace('<text x="40" y="80"', '<text x="40" y="80" style="fill:u\\72l(#a)"', 1)
    assert "css-escape" in rules(lint_svg.lint_text(text, "x.svg"))


@pytest.mark.parametrize(
    "attr,value",
    [
        ("fill", "u\\72l(https://h/x)"),
        ("fill", "u&#92;72l(#a)"),
        ("filter", "image-set(a 1x)"),
        ("stroke", "cross-fade(#a,#b)"),
        ("clip-path", "src(a)"),
        ("data-x", "see http://h/x"),
        ("fill", "url(&amp;#92;&amp;#117;rl(x))"),
    ],
)
def test_lint_svg_presentation_attribute_hazards_rejected(attr, value):
    text = STATIC.replace('<text x="40" y="80"', f'<text x="40" y="80" {attr}="{value}"', 1)
    text = text.replace(' fill="#e9d437" font-family', " font-family", 1)  # no duplicate fill
    result = lint_svg.lint_text(text, "x.svg")
    assert rules(result) & {"css-forbidden", "css-escape"}, result.violations


def test_lint_svg_namespace_declarations_are_not_css():
    # xmlns values contain '://' but are namespace declarations, not attributes
    assert lint_svg.lint_text(STATIC, "x.svg").ok


def test_lint_svg_plain_css_and_attribute_values_still_pass():
    text = _with_style_element("text{fill:#e9d437;font-family:Georgia,serif}").replace(
        'font-family="Georgia, serif"', 'font-family="Georgia, serif" fill-opacity="1"', 1
    )
    result = lint_svg.lint_text(text, "x.svg")
    assert result.ok, result.violations


# --------------------------------------------------------------------------
# processing instructions

PI = '<?xml-stylesheet href="https://h/x.css"?>'


def test_lint_svg_xml_declaration_alone_passes():
    text = '<?xml version="1.0" encoding="UTF-8"?>\n' + STATIC
    result = lint_svg.lint_text(text, "x.svg", require_opaque_background=True)
    assert result.ok, result.violations


@pytest.mark.parametrize(
    "text",
    [
        PI + "\n" + STATIC,
        '<?xml version="1.0"?>\n' + PI + "\n" + STATIC,
        STATIC.replace("</svg>", PI + "</svg>"),
        STATIC.replace("<title>", PI + "<title>", 1),
        "<?XML-STYLESHEET href='https://h/x.css'?>" + STATIC,
        "<?php echo 1 ?>" + STATIC,
        STATIC.replace("<title>Fixture banner", "<title>&lt;?xml-stylesheet href=x?&gt;", 1),
    ],
)
def test_lint_svg_processing_instructions_rejected(text):
    assert "processing-instruction" in rules(lint_svg.lint_text(text, "x.svg"))


def test_lint_svg_second_xml_declaration_is_rejected():
    text = '<?xml version="1.0"?>' + STATIC.replace("</svg>", '<?xml version="1.0"?></svg>')
    assert not lint_svg.lint_text(text, "x.svg").ok


# --------------------------------------------------------------------------
# --max-bytes


def test_lint_svg_max_bytes_library():
    size = len(STATIC.encode("utf-8"))
    assert lint_svg.lint_text(STATIC, "x.svg", max_bytes=size).ok
    result = lint_svg.lint_text(STATIC, "x.svg", max_bytes=size - 1)
    assert "too-large" in rules(result)
    assert lint_svg.lint_text(STATIC, "x.svg").ok  # default: no upper bound


def test_lint_svg_max_bytes_cli(tmp_path, capsys):
    f = tmp_path / "a.svg"
    f.write_text(STATIC, encoding="utf-8")
    size = f.stat().st_size
    assert lint_svg.main([str(f), "--max-bytes", str(size)]) == 0
    capsys.readouterr()
    assert lint_svg.main([str(f), "--max-bytes", str(size - 1)]) == 1
    assert "too-large" in capsys.readouterr().out
    assert lint_svg.main([str(f)]) == 0
