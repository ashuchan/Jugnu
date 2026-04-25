"""generate_blink_report() — per-URL markdown report.

One report per Blink: status, tier, record count, cost, consolidations triggered.
"""
from __future__ import annotations

from jugnu.contracts import Blink


def generate_blink_report(blink: Blink, *, consolidations_triggered: int = 0) -> str:
    lines: list[str] = [
        f"# Blink — {blink.url}",
        "",
        f"- **Status:** {blink.status}",
        f"- **Tier:** {blink.tier_used or '(none)'}",
        f"- **Records:** {len(blink.records)}",
        f"- **Confidence:** {blink.confidence:.2f}",
        f"- **LLM cost:** ${blink.llm_cost_usd:.4f}",
        f"- **Carry-forward days:** {blink.carry_forward_days}",
        f"- **Consolidations triggered:** {consolidations_triggered}",
    ]
    if blink.errors:
        lines += ["", "## Errors"]
        for err in blink.errors[:5]:
            lines.append(f"- {err}")
    return "\n".join(lines)
