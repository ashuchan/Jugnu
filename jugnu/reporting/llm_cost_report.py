"""build_cost_report() — per-prompt-stage cost breakdown read from the cost ledger."""
from __future__ import annotations

from pathlib import Path

from jugnu.observability.cost_ledger import CostLedger


def build_cost_report(
    ledger: CostLedger | str | Path,
    *,
    skill: str | None = None,
) -> str:
    """Render a markdown cost-by-stage / cost-by-model breakdown.

    Accepts a CostLedger instance or a path; instantiates the ledger if needed.
    """
    if not isinstance(ledger, CostLedger):
        ledger = CostLedger(ledger)

    by_stage = ledger.cost_by_stage(skill=skill)
    by_model = ledger.cost_by_model(skill=skill)
    by_url = ledger.cost_by_url(skill=skill)
    total = ledger.total_cost(skill=skill)

    lines: list[str] = [
        "# LLM Cost Breakdown",
        f"**Total:** ${total:.4f}",
        f"**Entries:** {ledger.entry_count()}",
        "",
        "## By prompt stage",
    ]
    for stage, cost in sorted(by_stage.items(), key=lambda kv: kv[1], reverse=True):
        lines.append(f"- `{stage}`: ${cost:.4f}")

    lines += ["", "## By model"]
    for model, cost in sorted(by_model.items(), key=lambda kv: kv[1], reverse=True):
        lines.append(f"- `{model or '(unknown)'}`: ${cost:.4f}")

    lines += ["", "## Top URLs by cost"]
    for url, cost in sorted(by_url.items(), key=lambda kv: kv[1], reverse=True)[:10]:
        short = (url[:80] + "...") if len(url) > 80 else url
        lines.append(f"- `{short}`: ${cost:.4f}")

    return "\n".join(lines)
