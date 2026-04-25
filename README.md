# Jugnu 🪲

**Self-learning web crawler for domain-specific data extraction.**

Jugnu (Urdu: firefly) is a Python library that learns to extract structured data from any website
domain. It uses a six-prompt LLM architecture (via litellm) that grows smarter with every URL it
processes — reducing LLM cost over time via `SkillMemory`.

## Quickstart

```python
import asyncio
from jugnu import Jugnu, Skill, CrawlInput
from jugnu.skill import OutputSchema, SourceHint, LiteLLMSettings

skill = Skill(
    name="apartment_availability",
    version="1.0",
    description="Extract unit-level rent from apartment websites",
    output_schema=OutputSchema(
        fields=["unit_id", "rent_low", "bedrooms", "available_date"],
        minimum_fields=["rent_low", "bedrooms"],
        primary_key="unit_id",
        merging_keys=["unit_id"],
    ),
    general_instructions="Extract all available apartment units. Minimum: rent and bedrooms.",
    source_hints=[SourceHint(platform="rentcafe", api_patterns=["/api/getApartments"])],
    llm=LiteLLMSettings(model="openai/gpt-4o-mini"),
)

async def main():
    jugnu = Jugnu(skill=skill)
    results = await jugnu.crawl({"https://example.com": CrawlInput()})
    for url, blink in results.items():
        print(f"{url}: {len(blink.records)} records, tier={blink.tier_used}")
        # persist for next run:
        # store.save_skill_memory(skill.name, blink.llm_profile)
        # store.save_scrape_profile(url, blink.scrape_profile)

asyncio.run(main())
```

## Module Map (firefly metaphor)

| Module | Metaphor | Responsibility |
|--------|----------|----------------|
| `ember/` | Heat that ignites | Fetch: Playwright, stealth, proxy, rate limiter |
| `lantern/` | Shape of the light | Discovery: link/API ranking, Prompt-1 |
| `glow/` | Emitted light | Extraction: adapter registry, tier cascade, normalizer |
| `spark/` | First flash | LLM: litellm, 6 prompts, SkillMemory, consolidator |
| `Skill` | Behavioural instinct | User input: schema, hints, LLM settings |
| `SkillMemory` | Pattern remembered | Living domain memory, self-improving across URLs |
| `Blink` | Single flash | Per-URL result: records + profiles + cost |
| `Swarm` | Coordinating fireflies | Concurrency: asyncio semaphore pool |

## SkillMemory Lifecycle

```
Jugnu(skill=skill)         → SkillMemory v1  (Prompt-5 warmup, no page load)
  crawl() URL #1–50        → pending_signals accumulates
  URL #50 complete         → Prompt-6 consolidation → SkillMemory v2
  run complete             → Prompt-6 run-end → SkillMemory vN
  blink.llm_profile        → persist for next run

Next run: Jugnu(skill=skill, skill_memory=persisted) → warmup SKIPPED
```

## Installation

```bash
pip install jugnu
# from source:
pip install -e ".[dev]"
```

## License

Apache 2.0
