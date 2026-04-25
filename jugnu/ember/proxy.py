"""Proxy configuration + provider abstraction for Ember.

Three pluggable provider implementations cover the common cases:

  StaticProxyProvider     — one server reused for every fetch.
  RotatingProxyProvider   — health-scored pool over a list of servers, picks
                            the healthiest non-quarantined entry per fetch.
  BrightDataProvider      — Bright Data residential / datacenter proxy with
                            optional URL-sticky session IDs (residential
                            scraping where a multi-page session needs IP
                            continuity per property).

Callers can also implement `ProxyProvider` directly to plug in any custom
selection / sessioning strategy.

The provider is the only thing Ember talks to: ProxyConfig describes the
server + auth, and the provider decides which one to hand back per URL and
how to react to success/failure feedback.
"""
from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit

from jugnu.ember.proxy_pool import ProxyPool


@dataclass(frozen=True)
class ProxyConfig:
    """One proxy endpoint. Auth is held separately so we can format it for
    Playwright (separate fields) or httpx (auth baked into the URL).
    """

    server: str
    username: str | None = None
    password: str | None = None

    def to_playwright(self) -> dict[str, str]:
        out: dict[str, str] = {"server": self.server}
        if self.username:
            out["username"] = self.username
        if self.password:
            out["password"] = self.password
        return out

    def to_httpx_url(self) -> str:
        """Server URL with auth embedded (httpx.AsyncClient(proxy=...) format)."""
        if not self.username:
            return self.server
        parts = urlsplit(self.server)
        creds = quote(self.username, safe="")
        if self.password:
            creds = f"{creds}:{quote(self.password, safe='')}"
        netloc = f"{creds}@{parts.netloc}"
        return urlunsplit(
            (parts.scheme, netloc, parts.path, parts.query, parts.fragment)
        )

    @classmethod
    def parse(cls, raw: str) -> ProxyConfig:
        """Parse a proxy URL that may include user:pass@host:port credentials."""
        parts = urlsplit(raw)
        if parts.username or parts.password:
            stripped_netloc = parts.hostname or ""
            if parts.port:
                stripped_netloc = f"{stripped_netloc}:{parts.port}"
            server = urlunsplit(
                (parts.scheme, stripped_netloc, parts.path, parts.query, parts.fragment)
            )
            return cls(server=server, username=parts.username, password=parts.password)
        return cls(server=raw)


class ProxyProvider(ABC):
    """Per-fetch proxy selection. Implementations may also track per-proxy
    health via the report_* hooks; default no-op implementations keep custom
    providers terse when no rotation/scoring is needed.
    """

    @abstractmethod
    def select(self, url: str) -> ProxyConfig | None:
        """Return the ProxyConfig to use for `url`, or None for a direct fetch."""

    def report_success(self, url: str, config: ProxyConfig) -> None:
        return None

    def report_failure(
        self,
        url: str,
        config: ProxyConfig,
        severity: str = "soft",
    ) -> None:
        return None

    def has_proxies(self) -> bool:
        """True if this provider can ever return a non-None config.

        Used by Ember to decide whether to enable per-context proxy mode at
        browser launch.
        """
        return True


class NoProxyProvider(ProxyProvider):
    """Sentinel — always returns None. Lets Ember treat the no-proxy case
    uniformly without sprinkling None checks everywhere.
    """

    def select(self, url: str) -> ProxyConfig | None:
        return None

    def has_proxies(self) -> bool:
        return False


class StaticProxyProvider(ProxyProvider):
    """One ProxyConfig reused for every fetch."""

    def __init__(self, config: ProxyConfig | None) -> None:
        self._config = config

    def select(self, url: str) -> ProxyConfig | None:
        return self._config

    def has_proxies(self) -> bool:
        return self._config is not None


class RotatingProxyProvider(ProxyProvider):
    """Health-scored pool over a list of ProxyConfigs.

    Picks the healthiest non-quarantined entry per fetch. Reports success/
    failure into the underlying ProxyPool so consistently-failing proxies are
    quarantined. `severity="hard"` is a stronger penalty (used for 403/captcha/
    auth failures); the default soft failure is for transient timeouts.
    """

    def __init__(self, configs: list[ProxyConfig]) -> None:
        if not configs:
            raise ValueError("RotatingProxyProvider requires at least one ProxyConfig")
        self._configs = {c.server: c for c in configs}
        self._pool = ProxyPool([c.server for c in configs])

    def select(self, url: str) -> ProxyConfig | None:
        chosen = self._pool.select()
        if not chosen:
            return None
        return self._configs.get(chosen)

    def report_success(self, url: str, config: ProxyConfig) -> None:
        self._pool.report_success(config.server)

    def report_failure(
        self,
        url: str,
        config: ProxyConfig,
        severity: str = "soft",
    ) -> None:
        self._pool.report_failure(config.server, severity=severity)

    def has_proxies(self) -> bool:
        return bool(self._configs)


class BrightDataProvider(ProxyProvider):
    """Bright Data residential / datacenter proxy.

    Username format (per Bright Data docs):

      Rotating IP per request (default if sticky_session_per_url=False):
          brd-customer-{customer_id}-zone-{zone}[-country-{country}]

      Sticky session — same IP for the lifetime of a session ID. With
      sticky_session_per_url=True we derive a 16-char session ID from
      sha256(url) so multi-page crawls of the same property reuse the same
      exit IP, but two different properties land on different IPs:
          brd-customer-{customer_id}-zone-{zone}[-country-{country}]-session-{sid}

    Defaults to brd.superproxy.io:22225 — Bright Data's standard endpoint.
    """

    def __init__(
        self,
        customer_id: str,
        zone: str,
        password: str,
        host: str = "brd.superproxy.io",
        port: int = 22225,
        sticky_session_per_url: bool = True,
        country: str | None = None,
        scheme: str = "http",
    ) -> None:
        if not customer_id or not zone or not password:
            raise ValueError("BrightDataProvider requires customer_id, zone, password")
        self._customer_id = customer_id
        self._zone = zone
        self._password = password
        self._server = f"{scheme}://{host}:{port}"
        self._sticky = sticky_session_per_url
        self._country = country.lower() if country else None

    def select(self, url: str) -> ProxyConfig | None:
        username = self._build_username(url)
        return ProxyConfig(server=self._server, username=username, password=self._password)

    def has_proxies(self) -> bool:
        return True

    @classmethod
    def from_env(cls) -> BrightDataProvider | None:
        """Construct from PROXY_* env vars if PROXY_PROVIDER=brightdata.

        Reads:
          PROXY_USERNAME or PROXY_BRIGHTDATA_CUSTOMER_ID
          PROXY_BRIGHTDATA_ZONE                    (required if PROXY_USERNAME absent)
          PROXY_PASSWORD
          PROXY_HOST  (default brd.superproxy.io)
          PROXY_PORT  (default 22225)
          PROXY_BRIGHTDATA_COUNTRY                 (optional, e.g. "us")
          PROXY_BRIGHTDATA_STICKY_PER_URL          ("0" disables; default on)
        Returns None if required vars are missing.
        """
        if (os.getenv("PROXY_PROVIDER") or "").strip().lower() != "brightdata":
            return None
        customer_id = os.getenv("PROXY_BRIGHTDATA_CUSTOMER_ID") or os.getenv("PROXY_USERNAME")
        zone = os.getenv("PROXY_BRIGHTDATA_ZONE")
        password = os.getenv("PROXY_PASSWORD")
        if not customer_id or not zone or not password:
            return None
        host = os.getenv("PROXY_HOST", "brd.superproxy.io")
        port = int(os.getenv("PROXY_PORT", "22225"))
        country = os.getenv("PROXY_BRIGHTDATA_COUNTRY")
        sticky = (os.getenv("PROXY_BRIGHTDATA_STICKY_PER_URL", "1") or "1").strip() != "0"
        return cls(
            customer_id=customer_id,
            zone=zone,
            password=password,
            host=host,
            port=port,
            country=country,
            sticky_session_per_url=sticky,
        )

    def _build_username(self, url: str) -> str:
        parts = [f"brd-customer-{self._customer_id}", f"zone-{self._zone}"]
        if self._country:
            parts.append(f"country-{self._country}")
        if self._sticky:
            sid = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            parts.append(f"session-{sid}")
        return "-".join(parts)


def build_proxy_provider_from_settings(settings: object) -> ProxyProvider:
    """Materialise a ProxyProvider from a `ProxySettings`-shaped object.

    Selection order:
      1. settings.disabled True → NoProxyProvider
      2. brightdata block populated → BrightDataProvider
      3. rotating_servers populated → RotatingProxyProvider
      4. server populated → StaticProxyProvider
      5. otherwise → NoProxyProvider
    """
    if settings is None:
        return NoProxyProvider()
    if not getattr(settings, "enabled", True):
        return NoProxyProvider()

    bd_customer = getattr(settings, "brightdata_customer_id", None)
    bd_zone = getattr(settings, "brightdata_zone", None)
    bd_password = (
        getattr(settings, "brightdata_password", None)
        or getattr(settings, "password", None)
    )
    if bd_customer and bd_zone and bd_password:
        return BrightDataProvider(
            customer_id=bd_customer,
            zone=bd_zone,
            password=bd_password,
            host=getattr(settings, "brightdata_host", "brd.superproxy.io"),
            port=int(getattr(settings, "brightdata_port", 22225)),
            country=getattr(settings, "brightdata_country", None),
            sticky_session_per_url=bool(
                getattr(settings, "brightdata_sticky_per_url", True)
            ),
        )

    rotating = list(getattr(settings, "rotating_servers", []) or [])
    if rotating:
        return RotatingProxyProvider([ProxyConfig.parse(s) for s in rotating])

    server = getattr(settings, "server", None)
    if server:
        return StaticProxyProvider(
            ProxyConfig(
                server=server,
                username=getattr(settings, "username", None),
                password=getattr(settings, "password", None),
            )
        )

    return NoProxyProvider()


def build_proxy_provider_from_env() -> ProxyProvider:
    """Convenience: build a provider from environment variables.

    Recognises:
      PROXY_PROVIDER=brightdata        — see BrightDataProvider.from_env()
      PROXY_PROVIDER=rotating          — PROXY_POOL_URLS comma-separated
      PROXY_PROVIDER=static (or unset) — PROXY_SERVER + optional PROXY_USERNAME/PROXY_PASSWORD

    Returns NoProxyProvider() if nothing is configured.
    """
    provider = (os.getenv("PROXY_PROVIDER") or "").strip().lower()
    if provider == "brightdata":
        bd = BrightDataProvider.from_env()
        return bd or NoProxyProvider()
    if provider == "rotating":
        raw = os.getenv("PROXY_POOL_URLS", "")
        servers = [s.strip() for s in raw.split(",") if s.strip()]
        if servers:
            return RotatingProxyProvider([ProxyConfig.parse(s) for s in servers])
        return NoProxyProvider()
    server = os.getenv("PROXY_SERVER")
    if server:
        return StaticProxyProvider(
            ProxyConfig(
                server=server,
                username=os.getenv("PROXY_USERNAME"),
                password=os.getenv("PROXY_PASSWORD"),
            )
        )
    return NoProxyProvider()


def classify_failure_severity(status_code: int, error: str | None) -> str:
    """Map a fetch outcome to a ProxyPool severity ("hard" or "soft").

    Hard: 403/407/451/captcha — likely the proxy itself is burned/blocked.
    Soft: 5xx, timeouts, network errors — could be transient, lighter penalty.
    """
    hard_codes = {403, 407, 451}
    if status_code in hard_codes:
        return "hard"
    if error and ("captcha" in error.lower() or "auth" in error.lower()):
        return "hard"
    return "soft"
