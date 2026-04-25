"""build_run_report() — run-wide summary with tier distribution and costs.

Includes SkillMemory version progression and consolidation totals so a reader
can see how the brain evolved during the run.
"""
from __future__ import annotations

from collections import Counter

from jugnu.contracts import Blink, CrawlStatus
from jugnu.spark.skill_memory import SkillMemory


def build_run_report(
    results: dict[str, Blink],
    *,
    skill_name: str = "",
    memory: SkillMemory | None = None,
    warmup_cost_usd: float = 0.0,
) -> str:
    total = len(results)
    status_counts: Counter[str] = Counter(str(b.status) for b in results.values())
    success = status_counts.get(str(CrawlStatus.SUCCESS), 0)
    partial = status_counts.get(str(CrawlStatus.PARTIAL), 0)
    failed = status_counts.get(str(CrawlStatus.FAILED), 0)
    carry = status_counts.get(str(CrawlStatus.CARRY_FORWARD), 0)
    tier_counts: Counter[str] = Counter(b.tier_used or "(none)" for b in results.values())

    url_cost = sum(b.llm_cost_usd for b in results.values())
    consolidation_cost = memory.total_consolidation_cost_usd if memory else 0.0
    total_cost = url_cost + consolidation_cost + warmup_cost_usd

    lines: list[str] = [
        "# Jugnu Run Report",
        f"**Skill:** {skill_name}",
        f"**URLs:** {total}",
        "",
        "## Outcomes",
        f"- success: {success}",
        f"- partial: {partial}",
        f"- failed: {failed}",
        f"- carry_forward: {carry}",
        "",
        "## Tier distribution",
    ]
    for tier, count in tier_counts.most_common():
        lines.append(f"- `{tier}`: {count}")

    lines += [
        "",
        "## LLM cost",
        f"- url-level: ${url_cost:.4f}",
        f"- warmup: ${warmup_cost_usd:.4f}",
        f"- consolidation: ${consolidation_cost:.4f}",
        f"- **total: ${total_cost:.4f}**",
    ]

    if memory is not None:
        lines += [
            "",
            "## SkillMemory progression",
            f"- memory_version: {memory.memory_version}",
            f"- consolidations: {len(memory.consolidation_log)}",
            f"- pending signals: {memory.pending_signal_count()}",
            f"- known platform fingerprints: {len(memory.platform_fingerprints)}",
        ]
        if memory.consolidation_log:
            lines.append("")
            lines.append("### Consolidation log")
            for entry in memory.consolidation_log[-5:]:
                lines.append(
                    f"- {entry.timestamp or ''} `{entry.triggered_by}`: "
                    f"v{entry.memory_version_before}→v{entry.memory_version_after}, "
                    f"{entry.signals_processed} signals, ${entry.cost_usd:.4f}"
                )

    return "\n".join(lines)
