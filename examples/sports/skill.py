"""Sports data crawler example Skill."""
from __future__ import annotations

from jugnu.skill import JugnuSettings, OutputSchema, Skill, SourceHint

sports_skill = Skill(
    name="sports_stats",
    version="1.0.0",
    description="Extract sports statistics including player name, team, position, and key stats.",
    output_schema=OutputSchema(
        fields=["player_name", "team", "position", "games_played", "score", "season", "stat_url"],
        primary_key="stat_url",
        merging_keys=["player_name", "team"],
        minimum_fields=["player_name", "team"],
    ),
    source_hints=[
        SourceHint(
            link_keywords=["player", "stats", "roster", "season", "league", "standings"],
            api_patterns=["/api/players", "/stats/", "/v1/sports", "/leagues/"],
        )
    ],
    jugnu_settings=JugnuSettings(
        link_confidence_threshold=0.4,
        max_concurrent_crawls=8,
        carry_forward_on_failure=True,
    ),
)
