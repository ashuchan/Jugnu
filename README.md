# Jugnu

**Self-learning web crawler for domain-specific data extraction.**

Jugnu is a domain-agnostic open-source Python library that extracts structured records from any website. You define a `Skill` (what to extract), Jugnu handles the rest — including learning from each crawl via `SkillMemory`.

## Installation

```bash
pip install jugnu
# or for development:
git clone https://github.com/ashuchan/jugnu && cd jugnu
pip install -e '.[dev]'
pip install playwright && playwright install chromium
```

## Quickstart

```python
import asyncio, json
from jugnu import Jugnu, Skill, SkillMemory
from jugnu.skill import OutputSchema, SourceHint
from jugnu.contracts import CrawlInput

# 1. Define your Skill
skill = Skill(
    name="product_catalog",
    version="1.0.0",
    description="Extract product listings",
    output_schema=OutputSchema(
        fields=["name", "price", "sku", "url"],
        primary_key="sku",
        minimum_fields=["name", "price"],
    ),
    source_hints=[SourceHint(link_keywords=["product", "item", "catalog"])],
)

async def main():
    # 2. Optional: load persisted SkillMemory from previous run
    # memory = SkillMemory.model_validate(json.load(open("memory.json")))
    memory = None

    jugnu = Jugnu(skill=skill, skill_memory=memory)

    # 3. Warm-up (Prompt-5): seed SkillMemory WITHOUT fetching any URL
    memory = await jugnu.warm_up()

    # 4. Crawl
    urls = {
        "https://example-shop.com/products": CrawlInput(url="https://example-shop.com/products"),
    }
    results = await jugnu.crawl(urls)

    # 5. Use results
    for url, blink in results.items():
        print(f"{url}: {len(blink.records)} records ({blink.status})")

    # 6. Persist SkillMemory for next run
    # json.dump(memory.model_dump(mode='json'), open("memory.json", "w"))

asyncio.run(main())
```

## Module Map

| Module | Firefly Name | Role |
|--------|-------------|------|
| `jugnu/ember/` | **Ember** | Fetch layer (Playwright, stealth, proxy, rate limiter) |
| `jugnu/lantern/` | **Lantern** | Discovery (link ranking, API heuristics) |
| `jugnu/glow/` | **Glow** | Extraction cascade (JSON-LD → API JSON → Microdata → DOM → LLM) |
| `jugnu/spark/` | **Spark** | LLM teacher (6 prompts, SkillMemory, consolidation) |
| `jugnu/skill.py` | **Skill** | User input: schema, hints, settings |
| `jugnu/contracts.py` | — | Core types: Blink, CrawlStatus, CrawlInput, FetchResult |
| `jugnu/profile.py` | — | ScrapeProfile: per-URL learned knowledge |

## SkillMemory Lifecycle

```
Skill defined by user
       │
       ▼
  warm_up()  ──── Prompt-5 (no URL fetch) ────► SkillMemory created
       │
       ▼
  crawl(urls)
    ├── per URL: Prompts 1, 2, 4 ──► ImprovementSignals appended
    ├── every 50 signals: Prompt-6 batch consolidation
    ├── 3 new platform confirms: Prompt-6 smart trigger
    └── run end: Prompt-6 final consolidation
       │
       ▼
  Blink.llm_profile = SkillMemory  (same object on every Blink)
       │
       ▼
  Caller persists SkillMemory.json  ──► reused next run
```

## 6-Prompt Architecture

| # | Name | When | Inputs | Returns |
|---|------|------|--------|--------|
| 1 | Discovery | Per URL — after fetch, before extraction | `prompt1_context`, `general_instructions`, `output_fields`, `minimum_fields`, `known_noise_patterns`, candidate APIs/links | `ranked_apis`, `ranked_links`, `improvement_signal` |
| 2 | Extraction | Per URL — when deterministic tiers fail | `prompt2_context`, `general_instructions`, `output_schema`, `minimum_fields`, `confirmed_field_synonyms`, fit_markdown | `records`, `field_mappings`, `improvement_signal` |
| 3 | Merge | When `CrawlInput.previous_records` is non-empty AND new records were extracted | `general_instructions`, `primary_key`, `merging_keys`, existing & new records | `merge_decisions`, `merged_records` |
| 4 | External Rank | When `minimum_fields` are still missing AND `max_external_depth > 0` | `prompt4_context`, `general_instructions`, `missing_fields`, `known_noise_patterns`, external links | `ranked_external_links`, `improvement_signal` |
| 5 | Warmup | Once at session start (or on stale memory) — no URL fetched | `general_instructions`, `output_fields`, `minimum_fields`, `source_hints` | full initial SkillMemory including `prompt1_context`, `prompt2_context`, `prompt4_context` |
| 6 | Consolidation | Every N URLs (batch), 3+ new-platform confirmations (smart), or run end | current SkillMemory snapshot, accumulated `improvement_signals`, batch stats | rewritten SkillMemory + log entry |

Every prompt template lives in `jugnu/spark/prompts/*.txt` and is rendered by
`render_template()`. Prompts 1–4 must always return an `improvement_signal`;
those signals accumulate in `SkillMemory.pending_signals` and feed Prompt-6.

## Examples

- `examples/real_estate/` — property listings
- `examples/news/` — news articles
- `examples/finance/` — stock/market data
- `examples/sports/` — player stats

## Running Tests

```bash
pytest . --ignore=examples --ignore=.jugnu -v
```

## Requirements

- Python ≥ 3.11
- playwright, pydantic ≥ 2.0, litellm, beautifulsoup4, markdownify

## License

Apache-2.0
