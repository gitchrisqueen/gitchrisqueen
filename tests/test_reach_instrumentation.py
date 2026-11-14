"""Offline tests for the optional page-view counting on the graph page and the UTM tags on README links."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_assets_reach", ROOT / "scripts" / "build_assets.py")
assets = importlib.util.module_from_spec(spec)
sys.modules["build_assets_reach"] = assets
spec.loader.exec_module(assets)

KEY = "phc_" + "A1b2C3d4E5f6G7h8I9j0K1l2"
OFF = {"posthog_key": ""}


def page(raw: dict) -> str:
    return assets.build_graph_page(assets.parse_analytics(raw))


# ------------------------------------------------------------- off by default

def test_committed_settings_file_has_exactly_the_three_fields_and_is_valid():
    raw = json.loads((ROOT / "data" / "analytics.json").read_text(encoding="utf-8"))
    assert set(raw) == {"posthog_key", "posthog_host", "posthog_assets_host"}
    assets.parse_analytics(raw)


def test_empty_key_means_no_script_no_network_and_no_posthog_text():
    html = page(OFF)
    low = html.lower()
    assert "posthog" not in low
    # the only address on the page is the visible link back to the profile
    assert re.findall(r"https?://[^\"' <]+", html) == ["https://github.com/gitchrisqueen"]
    assert "<script src" not in low and "createelement(\"script\")" not in low
    assert "fetch(" not in low and "xmlhttprequest" not in low and "sendbeacon" not in low
    assert assets.PRIVACY_LINE not in html and "page-view" not in html
    assert html.count("<script") == 1


def test_committed_page_matches_the_committed_analytics_settings():
    committed = (ROOT / "docs" / "graph" / "index.html").read_text(encoding="utf-8")
    settings = assets.load_analytics()
    assert page(settings) == committed
    if not settings["posthog_key"]:
        assert "posthog" not in committed.lower()


def test_missing_settings_file_means_off(monkeypatch, tmp_path):
    monkeypatch.setattr(assets, "ANALYTICS_PATH", tmp_path / "absent.json")
    assert assets.load_analytics()["posthog_key"] == ""


# ------------------------------------------------------------- on

def test_valid_key_adds_the_loader_the_privacy_settings_one_event_and_the_privacy_line():
    html = page({"posthog_key": KEY})
    assert json.dumps(KEY) in html
    assert "<script src" not in html.lower()  # the page never names a script address in markup
    assert '"https://us-assets.i.posthog.com"+"/static/array.js"' in html
    assert 'api_host:"https://us.i.posthog.com"' in html
    for setting in (
        "persistence:'memory'", "autocapture:false", "capture_pageview:true", "capture_pageleave:false",
        "disable_session_recording:true", "disable_surveys:true", "respect_dnt:true", "person_profiles:'never'",
    ):
        assert setting in html, setting
    assert html.count("posthog.capture(") == 1 and "graph_interact" in html
    assert "identify(" not in html and "alias(" not in html  # nothing identifies a visitor
    assert html.count(assets.PRIVACY_LINE) == 1
    assert 'id="privacy"' in html
    assert assets.PRIVACY_LINE == "Anonymous page-view counts, no cookies."


def test_hosts_can_be_the_eu_cloud_pair():
    html = page({"posthog_key": KEY, "posthog_host": "https://eu.i.posthog.com",
                 "posthog_assets_host": "https://eu-assets.i.posthog.com"})
    assert "https://eu-assets.i.posthog.com" in html and "us-assets" not in html


# ------------------------------------------------------------- malformed settings fail the build

@pytest.mark.parametrize("bad", [
    "phc_short",
    "phc_" + "a" * 19,
    "abc123",
    " " + KEY,
    KEY + "\n",
    KEY + '"});alert(1);//',
    "PHC_" + "a" * 24,
])
def test_malformed_key_fails(bad):
    with pytest.raises(SystemExit) as err:
        assets.parse_analytics({"posthog_key": bad})
    assert "posthog_key" in str(err.value)


def test_personal_api_key_fails_with_a_clear_message():
    with pytest.raises(SystemExit) as err:
        assets.parse_analytics({"posthog_key": "phx_" + "a" * 40})
    assert "personal API key" in str(err.value)


@pytest.mark.parametrize("raw", [
    {"posthog_key": 5},
    {"posthog_key": "", "posthog_ky": "typo"},
    {"posthog_key": "", "posthog_host": "https://evil.example"},
    {"posthog_key": "", "posthog_assets_host": "https://us-assets.i.posthog.com/x"},
    {"posthog_key": "", "posthog_assets_host": "http://us-assets.i.posthog.com"},
    [],
])
def test_other_malformed_settings_fail(raw):
    with pytest.raises(SystemExit):
        assets.parse_analytics(raw)


def test_a_bad_key_in_the_file_stops_the_whole_build(monkeypatch, tmp_path):
    path = tmp_path / "analytics.json"
    path.write_text(json.dumps({"posthog_key": "phx_" + "a" * 40}), encoding="utf-8")
    monkeypatch.setattr(assets, "ANALYTICS_PATH", path)
    with pytest.raises(SystemExit):
        assets.main(["--check"])
    with pytest.raises(SystemExit):
        assets.build_all()


# ------------------------------------------------------------- --check

def test_build_check_passes_on_the_committed_tree():
    res = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_assets.py"), "--check"],
                         capture_output=True, text=True, cwd=ROOT)
    assert res.returncode == 0, res.stderr


def test_build_check_notices_a_key_set_without_a_rebuild(monkeypatch, tmp_path, capsys):
    path = tmp_path / "analytics.json"
    path.write_text(json.dumps({"posthog_key": KEY}), encoding="utf-8")
    monkeypatch.setattr(assets, "ANALYTICS_PATH", path)
    assert assets.main(["--check"]) == 1
    assert "docs/graph/index.html" in capsys.readouterr().err


# ------------------------------------------------------------- UTM tags on README links

OWNED_HOSTS = ("christopherqueenconsulting.com", "chrisqueen.com")
GRAPH_URL_PREFIX = "https://gitchrisqueen.github.io/gitchrisqueen/graph/"
URL_RE = re.compile(r"https?://[^\s)\"'<>\]]+")


def is_owned(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return (any(host == d or host.endswith("." + d) for d in OWNED_HOSTS)
            or url.startswith(GRAPH_URL_PREFIX))


def readme_urls() -> list[str]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    text = re.sub(r"\[https?://[^\]\s]+\]", "", text)  # a URL shown as link text is not a link target
    return URL_RE.findall(text)


def test_every_owned_domain_link_carries_the_three_utm_parameters():
    owned = [u for u in readme_urls() if is_owned(u)]
    assert len(owned) >= 8, owned
    assert any(u.startswith(GRAPH_URL_PREFIX) for u in owned)
    for url in owned:
        query = parse_qs(urlsplit(url).query)
        for name in ("utm_source", "utm_medium", "utm_campaign"):
            assert query.get(name) and len(query[name]) == 1, f"{name} missing or repeated: {url}"
        assert query["utm_source"] == ["github"], url


def test_links_without_a_utm_tag_use_the_profile_readme_values():
    for url in readme_urls():
        if is_owned(url) and "utm_medium=readme" not in url:
            assert "utm_source=github&utm_medium=profile&utm_campaign=readme" in url, url


def test_no_third_party_link_is_tagged():
    third = [u for u in readme_urls() if not is_owned(u)]
    assert len(third) > 20
    for url in third:
        assert "utm_" not in url, url
