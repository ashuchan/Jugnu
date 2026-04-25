from __future__ import annotations

from pydantic import BaseModel, Field


class LiteLLMSettings(BaseModel):
    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout_seconds: int = 60
    max_retries: int = 2
    extra_params: dict = Field(default_factory=dict)


class VisionLLMSettings(BaseModel):
    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.0
    max_tokens: int = 2048
    timeout_seconds: int = 60
    max_retries: int = 2


class ScreenshotSettings(BaseModel):
    enabled: bool = False
    full_page: bool = True
    max_screenshots_per_url: int = 2
    width: int = 1280
    height: int = 900


class OutputSchema(BaseModel):
    fields: list[str]
    primary_key: str | None = None
    merging_keys: list[str] = []
    minimum_fields: list[str]
    json_schema: dict = Field(default_factory=dict)


class SourceHint(BaseModel):
    platform: str | None = None
    api_patterns: list[str] = []
    link_keywords: list[str] = []
    dom_selectors: dict[str, str] = {}


class JugnuSettings(BaseModel):
    link_confidence_threshold: float = 0.4
    max_external_depth: int = 0
    max_llm_calls_per_url: int = 3
    max_concurrent_crawls: int = 0
    carry_forward_on_failure: bool = True
    memory_consolidation_batch_size: int = 50
    memory_consolidation_smart_trigger_count: int = 3


class ProxySettings(BaseModel):
    """Declarative proxy configuration. Materialised into a ProxyProvider by
    `jugnu.ember.proxy.build_proxy_provider_from_settings`.

    Selection precedence at materialisation time:
      1. enabled=False → no-proxy
      2. brightdata_* fields populated → BrightDataProvider
      3. rotating_servers populated → RotatingProxyProvider (health-scored)
      4. server populated → StaticProxyProvider
      5. otherwise → no-proxy
    """

    enabled: bool = True

    # Static-proxy mode
    server: str | None = None
    username: str | None = None
    password: str | None = None

    # Rotating-pool mode (each entry may include user:pass@host:port)
    rotating_servers: list[str] = []

    # Bright Data mode (residential / datacenter)
    brightdata_customer_id: str | None = None
    brightdata_zone: str | None = None
    brightdata_password: str | None = None
    brightdata_host: str = "brd.superproxy.io"
    brightdata_port: int = 22225
    brightdata_country: str | None = None
    brightdata_sticky_per_url: bool = True


class Skill(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str = ""
    output_schema: OutputSchema
    source_hints: list[SourceHint] = []
    llm_settings: LiteLLMSettings = Field(default_factory=LiteLLMSettings)
    vision_settings: VisionLLMSettings = Field(default_factory=VisionLLMSettings)
    screenshot_settings: ScreenshotSettings = Field(default_factory=ScreenshotSettings)
    jugnu_settings: JugnuSettings = Field(default_factory=JugnuSettings)
    proxy_settings: ProxySettings = Field(default_factory=ProxySettings)
    custom_instructions: str = ""
    negative_keywords: list[str] = []
