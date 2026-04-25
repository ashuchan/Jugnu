"""Example runner for real-estate skill."""
from __future__ import annotations

import asyncio
import json

from jugnu.contracts import CrawlInput
from jugnu.crawler import Jugnu
from jugnu.observability.metrics import CrawlMetrics
from jugnu.reporting.report_builder import build_report

from examples.real_estate.skill import real_estate_skill


async def main() -> None:
    # Load persisted SkillMemory if available (caller responsibility)
    skill_memory = None

    jugnu = Jugnu(skill=real_estate_skill, skill_memory=skill_memory)

    # Warm-up: Prompt-5 generates initial SkillMemory (no URL fetch)
    memory = await jugnu.warm_up()
    print(f"Warm-up complete. Cost: ${memory.warmup_cost_usd:.4f}")

    # Example URLs (replace with real targets)
    urls = {
        "https://example-realty.com/listings": CrawlInput(url="https://example-realty.com/listings"),
    }

    results = await jugnu.crawl(urls)
    metrics = CrawlMetrics.from_results(results, skill_name=real_estate_skill.name)
    print(metrics.summary())
    print(build_report(results, skill_name=real_estate_skill.name))

    # Persist memory for next run (caller responsibility)
    # with open("real_estate_memory.json", "w") as f:
    #     json.dump(memory.model_dump(mode="json"), f, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
