from __future__ import annotations

import asyncio
import pytest

from jugnu.contracts import FetchResult
from jugnu.ember.captcha_detect import is_captcha_page
from jugnu.ember.change_detector import content_fingerprint, has_content_changed
from jugnu.ember.fetcher import Ember
from jugnu.ember.proxy_pool import ProxyPool
from jugnu.ember.rate_limiter import RateLimiter
from jugnu.ember.stealth import StealthConfig


def test_captcha_detect_positive():
    html = "<html><body>Please solve the recaptcha</body></html>"
    assert is_captcha_page(html) is True


def test_captcha_detect_negative():
    html = "<html><body>Welcome to our store</body></html>"
    assert is_captcha_page(html) is False


def test_captcha_detect_hcaptcha():
    html = "<html><script src='https://js.hcaptcha.com/1/api.js'></script></html>"
    assert is_captcha_page(html) is True


def test_content_fingerprint_deterministic():
    html = "<html>Hello World</html>"
    assert content_fingerprint(html) == content_fingerprint(html)


def test_content_fingerprint_length():
    assert len(content_fingerprint("<html></html>")) == 32


def test_has_content_changed_same():
    html = "<html>Same</html>"
    fp = content_fingerprint(html)
    assert has_content_changed(html, fp) is False


def test_has_content_changed_different():
    html1 = "<html>Version 1</html>"
    html2 = "<html>Version 2</html>"
    fp = content_fingerprint(html1)
    assert has_content_changed(html2, fp) is True


def test_proxy_pool_empty():
    pool = ProxyPool()
    assert pool.is_empty() is True
    assert pool.next() is None


def test_proxy_pool_round_robin():
    pool = ProxyPool(["proxy1:8080", "proxy2:8080"])
    assert pool.size() == 2
    first = pool.next()
    second = pool.next()
    third = pool.next()
    assert first != second
    assert third == first  # round-robin wraps


async def test_rate_limiter_acquire():
    rl = RateLimiter(requests_per_second=100.0, burst=10)
    # Should acquire without blocking at high RPS
    await rl.acquire("https://example.com/page1")
    await rl.acquire("https://example.com/page2")


async def test_ember_never_raises_on_bad_url():
    ember = Ember(timeout_ms=5000, max_retries=0)
    result = await ember.fetch("http://localhost:19999/nonexistent")
    assert isinstance(result, FetchResult)
    assert result.error is not None


async def test_stealth_config_defaults():
    sc = StealthConfig()
    assert "Mozilla" in sc.user_agent
    assert "Accept-Language" in sc.extra_headers
