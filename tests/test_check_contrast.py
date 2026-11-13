"""Offline tests for scripts/check_contrast.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cc = _load("check_contrast")


def pair(**kw):
    base = {"id": "p", "kind": "text", "foreground": "#e9d437", "background": "#0d1117"}
    base.update(kw)
    return base


def write(tmp_path, pairs):
    p = tmp_path / "colors.json"
    p.write_text(json.dumps({"version": 1, "pairs": pairs}))
    return str(p)


def test_contrast_known_ratios():
    assert cc.contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert cc.contrast_ratio("#fff", "#fff") == pytest.approx(1.0)
    assert cc.contrast_ratio("#e9d437", "#0d1117") == pytest.approx(12.56, abs=0.01)
    assert cc.contrast_ratio("#ffffff", "#1a7f37") == pytest.approx(5.08, abs=0.01)
    # symmetric
    assert cc.contrast_ratio("#0d1117", "#e9d437") == cc.contrast_ratio("#e9d437", "#0d1117")


def test_contrast_real_colors_file_passes(capsys):
    assert cc.main([str(ROOT / "assets" / "colors.json")]) == 0
    out = capsys.readouterr().out
    assert "0 error(s)" in out


def test_contrast_real_file_declares_required_pairs():
    data = json.loads((ROOT / "assets" / "colors.json").read_text())
    ids = {p["id"] for p in data["pairs"]}
    required = {
        "header-name", "header-role", "footer-text",
        "badge-label", "badge-passing", "badge-failing", "badge-no-status",
        "snake-light-level-0", "snake-dark-level-0",
    } | {f"snake-{t}-level-{n}" for t in ("light", "dark") for n in range(1, 5)}
    assert required <= ids
    for p in data["pairs"]:
        if p["id"].endswith("level-0"):
            assert p["exempt"] is True and p["reason"]
        if p["id"].startswith("badge-"):
            assert p["kind"] == "text"


def test_contrast_text_pair_below_4_5_fails(tmp_path, capsys):
    # gold #a89816 on white is about 2.93:1
    path = write(tmp_path, [pair(id="dark-gold-on-white", foreground="#a89816", background="#ffffff")])
    assert cc.main([path]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_contrast_text_pair_just_below_threshold_fails(tmp_path):
    # #777777 on white is 4.48:1, a classic near miss
    path = write(tmp_path, [pair(foreground="#777777", background="#ffffff")])
    assert cc.main([path]) == 1


def test_contrast_graphic_threshold_is_3(tmp_path):
    # #8f7f10 on white is ~4.03:1: fails as text, passes as graphic
    assert cc.main([write(tmp_path, [pair(foreground="#8f7f10", background="#ffffff")])]) == 1
    assert cc.main([write(tmp_path, [pair(kind="graphic", foreground="#8f7f10", background="#ffffff")])]) == 0
    assert cc.main([write(tmp_path, [pair(kind="graphic", foreground="#b8a61c", background="#ffffff")])]) == 1


def test_contrast_exempt_graphic_needs_reason(tmp_path):
    p = pair(kind="graphic", foreground="#ebedf0", background="#ffffff", exempt=True)
    assert cc.main([write(tmp_path, [p])]) == 1
    p["reason"] = "empty cell"
    assert cc.main([write(tmp_path, [p])]) == 0


def test_contrast_text_cannot_be_exempt(tmp_path):
    p = pair(foreground="#777777", background="#ffffff", exempt=True, reason="no")
    assert cc.main([write(tmp_path, [p])]) == 1


@pytest.mark.parametrize(
    "bad",
    [
        {"foreground": "e9d437"},
        {"foreground": "#e9d43780"},
        {"foreground": "gold"},
        {"kind": "large-text"},
        {"id": "Bad Id"},
    ],
)
def test_contrast_malformed_pair_fails(tmp_path, bad):
    assert cc.main([write(tmp_path, [pair(**bad)])]) == 1


def test_contrast_duplicate_id_fails(tmp_path):
    assert cc.main([write(tmp_path, [pair(), pair()])]) == 1


def test_contrast_empty_or_unreadable(tmp_path):
    assert cc.main([write(tmp_path, [])]) == 1
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert cc.main([str(bad)]) == 1
    assert cc.main([str(tmp_path / "missing.json")]) == 1
