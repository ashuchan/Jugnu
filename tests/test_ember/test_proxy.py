"""Coverage for the proxy abstraction (jugnu/ember/proxy.py) and the
Ember-side wiring that consumes it."""
from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest
import respx
from httpx import Response

from jugnu.ember.fetcher import Ember
from jugnu.ember.proxy import (
    BrightDataProvider,
    NoProxyProvider,
    ProxyConfig,
    RotatingProxyProvider,
    StaticProxyProvider,
    build_proxy_provider_from_env,
    build_proxy_provider_from_settings,
    classify_failure_severity,
)
from jugnu.skill import ProxySettings

# ---------------------------------------------------------------------------
# ProxyConfig
# ---------------------------------------------------------------------------


def test_proxy_config_to_playwright_strips_empty_creds():
    cfg = ProxyConfig(server="http://prox:8080")
    assert cfg.to_playwright() == {"server": "http://prox:8080"}


def test_proxy_config_to_playwright_includes_creds():
    cfg = ProxyConfig(server="http://prox:8080", username="u", password="p")
    out = cfg.to_playwright()
    assert out == {"server": "http://prox:8080", "username": "u", "password": "p"}


def test_proxy_config_to_httpx_url_no_creds():
    assert ProxyConfig(server="http://prox:8080").to_httpx_url() == "http://prox:8080"


def test_proxy_config_to_httpx_url_with_creds_quotes_specials():
    cfg = ProxyConfig(server="http://prox:8080", username="u@example", password="p:w")
    url = cfg.to_httpx_url()
    # "@" in the username and ":" in the password must be percent-encoded so
    # urlsplit on the result still recovers the host correctly.
    assert "u%40example" in url
    assert "p%3Aw" in url
    assert url.endswith("@prox:8080")


def test_proxy_config_parse_with_inline_creds():
    cfg = ProxyConfig.parse("http://user:pass@prox.example:8080/path")
    assert cfg.server == "http://prox.example:8080/path"
    assert cfg.username == "user"
    assert cfg.password == "pass"


def test_proxy_config_parse_without_creds():
    cfg = ProxyConfig.parse("http://prox.example:8080")
    assert cfg.server == "http://prox.example:8080"
    assert cfg.username is None
    assert cfg.password is None


# ---------------------------------------------------------------------------
# Static / NoProxy
# ---------------------------------------------------------------------------


def test_static_provider_returns_same_config_per_url():
    cfg = ProxyConfig(server="http://prox:8080")
    p = StaticProxyProvider(cfg)
    assert p.select("https://a.example") is cfg
    assert p.select("https://b.example") is cfg
    assert p.has_proxies()


def test_static_provider_empty_has_no_proxies():
    p = StaticProxyProvider(None)
    assert p.select("https://x") is None
    assert not p.has_proxies()


def test_no_proxy_provider():
    p = NoProxyProvider()
    assert p.select("anything") is None
    assert not p.has_proxies()


# ---------------------------------------------------------------------------
# RotatingProxyProvider
# ---------------------------------------------------------------------------


def test_rotating_provider_picks_a_proxy():
    configs = [
        ProxyConfig(server="http://a:1"),
        ProxyConfig(server="http://b:1"),
        ProxyConfig(server="http://c:1"),
    ]
    p = RotatingProxyProvider(configs)
    chosen = p.select("https://x")
    assert chosen is not None
    assert chosen.server in {"http://a:1", "http://b:1", "http://c:1"}


def test_rotating_provider_quarantines_after_hard_failures():
    configs = [
        ProxyConfig(server="http://bad:1"),
        ProxyConfig(server="http://good:1"),
    ]
    p = RotatingProxyProvider(configs)
    # Hammer "bad" with hard failures until it quarantines (each -0.25 from 1.0,
    # quarantined when health < 0.25 — so 4 hits push it to 0.0).
    bad_cfg = ProxyConfig(server="http://bad:1")
    for _ in range(4):
        p.report_failure("https://x", bad_cfg, severity="hard")
    # Subsequent selections should always pick "good".
    for _ in range(10):
        chosen = p.select("https://x")
        assert chosen is not None
        assert chosen.server == "http://good:1"


def test_rotating_provider_rejects_empty_pool():
    with pytest.raises(ValueError):
        RotatingProxyProvider([])


# ---------------------------------------------------------------------------
# BrightDataProvider
# ---------------------------------------------------------------------------


def test_brightdata_provider_basic_username():
    p = BrightDataProvider(
        customer_id="c1", zone="zr", password="pw",
        sticky_session_per_url=False,
    )
    cfg = p.select("https://a.example")
    assert cfg is not None
    assert cfg.username == "brd-customer-c1-zone-zr"
    assert cfg.password == "pw"
    assert cfg.server == "http://brd.superproxy.io:22225"


def test_brightdata_provider_country():
    p = BrightDataProvider(
        customer_id="c1", zone="zr", password="pw",
        country="US", sticky_session_per_url=False,
    )
    cfg = p.select("https://a.example")
    assert cfg.username == "brd-customer-c1-zone-zr-country-us"


def test_brightdata_provider_sticky_session_per_url():
    p = BrightDataProvider(
        customer_id="c1", zone="zr", password="pw",
        sticky_session_per_url=True,
    )
    cfg_a = p.select("https://prop-a.example/")
    cfg_b = p.select("https://prop-b.example/")
    cfg_a2 = p.select("https://prop-a.example/")
    expected_sid_a = hashlib.sha256(b"https://prop-a.example/").hexdigest()[:16]
    assert cfg_a.username.endswith(f"-session-{expected_sid_a}")
    # Same URL → same session ID (so multi-page crawls reuse the IP).
    assert cfg_a.username == cfg_a2.username
    # Different URL → different session ID.
    assert cfg_a.username != cfg_b.username


def test_brightdata_provider_validates_required_fields():
    with pytest.raises(ValueError):
        BrightDataProvider(customer_id="", zone="z", password="p")
    with pytest.raises(ValueError):
        BrightDataProvider(customer_id="c", zone="", password="p")
    with pytest.raises(ValueError):
        BrightDataProvider(customer_id="c", zone="z", password="")


def test_brightdata_from_env_returns_none_when_unset(monkeypatch):
    for k in [
        "PROXY_PROVIDER", "PROXY_USERNAME", "PROXY_PASSWORD",
        "PROXY_BRIGHTDATA_CUSTOMER_ID", "PROXY_BRIGHTDATA_ZONE",
    ]:
        monkeypatch.delenv(k, raising=False)
    assert BrightDataProvider.from_env() is None


def test_brightdata_from_env_assembles(monkeypatch):
    monkeypatch.setenv("PROXY_PROVIDER", "brightdata")
    monkeypatch.setenv("PROXY_BRIGHTDATA_CUSTOMER_ID", "ccc")
    monkeypatch.setenv("PROXY_BRIGHTDATA_ZONE", "residential1")
    monkeypatch.setenv("PROXY_PASSWORD", "secret")
    monkeypatch.setenv("PROXY_BRIGHTDATA_COUNTRY", "us")
    monkeypatch.setenv("PROXY_BRIGHTDATA_STICKY_PER_URL", "0")
    p = BrightDataProvider.from_env()
    assert p is not None
    cfg = p.select("https://x")
    assert cfg.username == "brd-customer-ccc-zone-residential1-country-us"
    assert cfg.password == "secret"


# ---------------------------------------------------------------------------
# build_proxy_provider_from_settings
# ---------------------------------------------------------------------------


def test_build_from_settings_disabled_returns_no_proxy():
    settings = ProxySettings(enabled=False, server="http://x:1")
    p = build_proxy_provider_from_settings(settings)
    assert isinstance(p, NoProxyProvider)


def test_build_from_settings_brightdata_wins_over_static():
    settings = ProxySettings(
        server="http://other:9",
        brightdata_customer_id="c1",
        brightdata_zone="zr",
        brightdata_password="pw",
    )
    p = build_proxy_provider_from_settings(settings)
    assert isinstance(p, BrightDataProvider)


def test_build_from_settings_rotating_wins_over_static():
    settings = ProxySettings(
        server="http://static:9",
        rotating_servers=["http://a:1", "http://b:1"],
    )
    p = build_proxy_provider_from_settings(settings)
    assert isinstance(p, RotatingProxyProvider)


def test_build_from_settings_static_only():
    settings = ProxySettings(server="http://only:1", username="u", password="p")
    p = build_proxy_provider_from_settings(settings)
    assert isinstance(p, StaticProxyProvider)
    cfg = p.select("any")
    assert cfg is not None
    assert cfg.username == "u"


def test_build_from_settings_default_no_proxy():
    p = build_proxy_provider_from_settings(ProxySettings())
    assert isinstance(p, NoProxyProvider)


def test_build_from_settings_none_input():
    p = build_proxy_provider_from_settings(None)
    assert isinstance(p, NoProxyProvider)


# ---------------------------------------------------------------------------
# build_proxy_provider_from_env
# ---------------------------------------------------------------------------


def test_build_from_env_static(monkeypatch):
    for k in ["PROXY_PROVIDER", "PROXY_POOL_URLS"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("PROXY_SERVER", "http://prox:8080")
    monkeypatch.setenv("PROXY_USERNAME", "u")
    monkeypatch.setenv("PROXY_PASSWORD", "p")
    p = build_proxy_provider_from_env()
    assert isinstance(p, StaticProxyProvider)
    cfg = p.select("any")
    assert cfg.username == "u"


def test_build_from_env_rotating(monkeypatch):
    monkeypatch.setenv("PROXY_PROVIDER", "rotating")
    monkeypatch.setenv("PROXY_POOL_URLS", "http://a:1, http://b:1 ,http://c:1")
    p = build_proxy_provider_from_env()
    assert isinstance(p, RotatingProxyProvider)


def test_build_from_env_no_config(monkeypatch):
    for k in [
        "PROXY_PROVIDER", "PROXY_SERVER", "PROXY_USERNAME", "PROXY_PASSWORD",
    ]:
        monkeypatch.delenv(k, raising=False)
    p = build_proxy_provider_from_env()
    assert isinstance(p, NoProxyProvider)


# ---------------------------------------------------------------------------
# classify_failure_severity
# ---------------------------------------------------------------------------


def test_classify_failure_severity_403_is_hard():
    assert classify_failure_severity(403, None) == "hard"


def test_classify_failure_severity_407_is_hard():
    assert classify_failure_severity(407, None) == "hard"


def test_classify_failure_severity_captcha_error_is_hard():
    assert classify_failure_severity(0, "captcha_detected") == "hard"


def test_classify_failure_severity_500_is_soft():
    assert classify_failure_severity(500, None) == "soft"


def test_classify_failure_severity_timeout_is_soft():
    assert classify_failure_severity(0, "ReadTimeout") == "soft"


# ---------------------------------------------------------------------------
# Ember integration — httpx path actually uses the proxy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ember_httpx_uses_proxy_url_from_static_provider():
    """We can't assert respx received a proxied request directly (respx
    intercepts the in-process httpx call before the proxy hop), but we CAN
    confirm Ember constructs the AsyncClient with the proxy URL we expected.
    """
    cfg = ProxyConfig(server="http://prox:8080", username="u", password="p")
    provider = StaticProxyProvider(cfg)
    ember = Ember(proxy_provider=provider, max_retries=0)

    captured: dict = {}
    real_client_cls = None

    import httpx as real_httpx
    real_client_cls = real_httpx.AsyncClient

    class _SpyClient(real_client_cls):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            super().__init__(*args, **kwargs)

    with respx.mock:
        respx.get("https://target.example").mock(
            return_value=Response(200, html="<html></html>")
        )
        with patch.object(real_httpx, "AsyncClient", _SpyClient):
            result = await ember.fetch("https://target.example")

    assert result.status_code == 200
    assert "proxy" in captured
    assert captured["proxy"] == cfg.to_httpx_url()


@pytest.mark.asyncio
async def test_ember_httpx_no_proxy_when_provider_returns_none():
    ember = Ember(proxy_provider=NoProxyProvider(), max_retries=0)
    captured: dict = {}
    import httpx as real_httpx

    class _SpyClient(real_httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            super().__init__(*args, **kwargs)

    with respx.mock:
        respx.get("https://target.example").mock(return_value=Response(200))
        with patch.object(real_httpx, "AsyncClient", _SpyClient):
            await ember.fetch("https://target.example")
    assert "proxy" not in captured


@pytest.mark.asyncio
async def test_ember_legacy_proxy_string_still_works():
    """Backward-compat: passing `proxy="http://x:8080"` wraps in a
    StaticProxyProvider so existing callers keep working."""
    ember = Ember(proxy="http://legacy:8080", max_retries=0)
    captured: dict = {}
    import httpx as real_httpx

    class _SpyClient(real_httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            super().__init__(*args, **kwargs)

    with respx.mock:
        respx.get("https://target.example").mock(return_value=Response(200))
        with patch.object(real_httpx, "AsyncClient", _SpyClient):
            await ember.fetch("https://target.example")
    assert captured.get("proxy") == "http://legacy:8080"


@pytest.mark.asyncio
async def test_ember_reports_success_to_provider():
    cfg = ProxyConfig(server="http://prox:8080")

    class _Spy(StaticProxyProvider):
        def __init__(self):
            super().__init__(cfg)
            self.successes = 0
            self.failures: list[str] = []

        def report_success(self, url, config):
            self.successes += 1

        def report_failure(self, url, config, severity="soft"):
            self.failures.append(severity)

    spy = _Spy()
    ember = Ember(proxy_provider=spy, max_retries=0)
    with respx.mock:
        respx.get("https://x.example").mock(return_value=Response(200, html="<html>ok</html>"))
        await ember.fetch("https://x.example")
    assert spy.successes == 1
    assert spy.failures == []


@pytest.mark.asyncio
async def test_ember_reports_hard_failure_on_403():
    cfg = ProxyConfig(server="http://prox:8080")

    class _Spy(StaticProxyProvider):
        def __init__(self):
            super().__init__(cfg)
            self.failures: list[str] = []

        def report_failure(self, url, config, severity="soft"):
            self.failures.append(severity)

    spy = _Spy()
    ember = Ember(proxy_provider=spy, max_retries=0)
    with respx.mock:
        respx.get("https://x.example").mock(return_value=Response(403))
        await ember.fetch("https://x.example")
    assert spy.failures == ["hard"]
