from __future__ import annotations

from jugnu.contracts import Blink


def build_report(results: dict[str, Blink], skill_name: str = "") -> str:
    lines: list[str] = [
        f"# Jugnu Crawl Report",
        f"Skill: {skill_name}",
        f"URLs crawled: {len(results)}",
        "",
        "| URL | Status | Records | Confidence | Tier |",
        "|-----|--------|---------|------------|------|",
    ]
    total_records = 0
    for url, blink in results.items():
        short_url = url[:60] + "..." if len(url) > 60 else url
        lines.append(
            f"| {short_url} | {blink.status} | {len(blink.records)} "
            f"| {blink.confidence:.2f} | {blink.tier_used} |"
        )
        total_records += len(blink.records)

    lines += [
        "",
        f"**Total records extracted:** {total_records}",
        f"**Total LLM cost:** ${sum(b.llm_cost_usd for b in results.values()):.4f}",
    ]

    failed = [url for url, b in results.items() if b.errors]
    if failed:
        lines += ["", "## Errors", ""]
        for url in failed:
            blink = results[url]
            lines.append(f"- `{url}`: {'; '.join(blink.errors[:3])}")

    return "\n".join(lines)


def blink_to_dict(blink: Blink) -> dict:
    return {
        "url": blink.url,
        "status": str(blink.status),
        "records": blink.records,
        "tier_used": blink.tier_used,
        "confidence": blink.confidence,
        "llm_cost_usd": blink.llm_cost_usd,
        "errors": blink.errors,
    }
