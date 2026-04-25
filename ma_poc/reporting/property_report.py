"""Per-property markdown report generator."""

from __future__ import annotations

from typing import Any

_UNREACHABLE_SIGNALS = (
    "ERR_SSL",
    "ERR_NAME_NOT_RESOLVED",
    "DNS",
    "timeout",
    "ETIMEDOUT",
    "ECONNREFUSED",
    "ENOTFOUND",
    "net::ERR_",
)


def _determine_verdict(scrape_result: dict[str, Any]) -> str:
    if scrape_result.get("_carry_forward"):
        return "CARRY_FORWARD"
    units = scrape_result.get("units") or []
    if len(units) > 0:
        return "SUCCESS"
    errors: list[str] = []
    for err in scrape_result.get("errors", []):
        errors.append(str(err))
    error_text = " ".join(errors)
    top_error = scrape_result.get("error", "")
    if top_error:
        error_text += " " + str(top_error)
    for signal in _UNREACHABLE_SIGNALS:
        if signal in error_text:
            return "FAILED_UNREACHABLE"
    return "FAILED_NO_DATA"


def generate_property_report(
    scrape_result: dict[str, Any],
    property_id: str,
    run_date: str,
    prior_units: list[dict[str, Any]] | None = None,
    issues: list[dict[str, Any]] | None = None,
) -> str:
    """Generate a per-property markdown report."""
    property_name = scrape_result.get("property_name", property_id)
    verdict = _determine_verdict(scrape_result)
    units = scrape_result.get("units") or []
    duration = scrape_result.get("scrape_duration_s", "n/a")
    llm_cost = scrape_result.get("llm_cost", 0.0)

    sections: list[str] = []
    sections.append(f"# {property_name} — {run_date}")
    sections.append(
        "\n".join([
            "## Status",
            "| | |",
            "|---|---|",
            f"| **Verdict** | {verdict} |",
            f"| Canonical ID | {property_id} |",
            f"| Units extracted | {len(units)} |",
            f"| Scrape duration | {duration}s |",
            f"| LLM cost | ${llm_cost:.4f} |" if isinstance(llm_cost, (int, float)) else f"| LLM cost | ${llm_cost} |",
        ])
    )

    detection = scrape_result.get("_detected_pms")
    if detection:
        pms_name = detection.get("name", "unknown")
        confidence = detection.get("confidence", "n/a")
        evidence_list = detection.get("evidence", [])
        evidence_str = ", ".join(str(e) for e in evidence_list) if evidence_list else "none"
        sections.append(
            "\n".join([
                "## Detection",
                "| | |",
                "|---|---|",
                f"| Detected PMS | {pms_name} (confidence {confidence}) |",
                f"| Evidence | {evidence_str} |",
                f"| Client account ID | {detection.get('client_account_id', 'n/a')} |",
                f"| Adapter used | {detection.get('adapter', 'n/a')} |",
            ])
        )

    steps = scrape_result.get("pipeline_steps")
    if steps:
        step_lines = ["## Pipeline", "| Step | Outcome | Notes |", "|---|---|---|"]
        for step in steps:
            step_lines.append(f"| {step.get('name','')} | {step.get('outcome','')} | {step.get('notes','')} |")
        sections.append("\n".join(step_lines))

    if prior_units is not None:
        prior_by_id = {u.get("unit_id") or u.get("unit_number", ""): u for u in prior_units}
        current_by_id = {u.get("unit_id") or u.get("unit_number", ""): u for u in units}
        new_ids = set(current_by_id) - set(prior_by_id)
        removed_ids = set(prior_by_id) - set(current_by_id)
        changed: list[str] = []
        for uid in sorted(set(current_by_id) & set(prior_by_id)):
            diffs = [f"{k}: {prior_by_id[uid].get(k)} -> {current_by_id[uid].get(k)}" for k in sorted(set(current_by_id[uid]) | set(prior_by_id[uid])) if not k.startswith("_") and current_by_id[uid].get(k) != prior_by_id[uid].get(k)]
            if diffs:
                changed.append(f"- **{uid}**: {'; '.join(diffs)}")
        if not new_ids and not removed_ids and not changed:
            sections.append("## Changes since last run\nNo changes detected.")
        else:
            change_lines = ["## Changes since last run"]
            if new_ids:
                change_lines.append(f"- **New units**: {', '.join(sorted(new_ids))}")
            if removed_ids:
                change_lines.append(f"- **Removed units**: {', '.join(sorted(removed_ids))}")
            if changed:
                change_lines.append("- **Updated units**:")
                change_lines.extend(f"  {c}" for c in changed)
            sections.append("\n".join(change_lines))

    if issues:
        issue_lines = ["## Issues"]
        for issue in issues:
            issue_lines.append(f"- **{issue.get('severity','INFO')}** {issue.get('code','')}: {issue.get('message','')}")
        sections.append("\n".join(issue_lines))

    llm_calls = scrape_result.get("llm_calls")
    if llm_calls:
        llm_lines = ["## LLM calls", "<details>", "<summary>Show LLM transcripts</summary>", ""]
        for i, call in enumerate(llm_calls, 1):
            llm_lines += [f"### Call {i} ({call.get('model','unknown')})", "", "**Prompt:**", f"```\n{call.get('prompt','')}\n```", "", "**Response:**", f"```\n{call.get('response','')}\n```", ""]
        llm_lines.append("</details>")
        sections.append("\n".join(llm_lines))

    return "\n\n".join(sections) + "\n"
