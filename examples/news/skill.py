"""News article crawler example Skill."""
from __future__ import annotations

from jugnu.skill import JugnuSettings, OutputSchema, Skill, SourceHint

news_skill = Skill(
    name="news_articles",
    version="1.0.0",
    description="Extract news articles including headline, author, published date, body summary, and URL.",
    output_schema=OutputSchema(
        fields=["headline", "author", "published_at", "summary", "article_url", "category"],
        primary_key="article_url",
        merging_keys=["headline"],
        minimum_fields=["headline", "article_url"],
    ),
    source_hints=[
        SourceHint(
            link_keywords=["article", "news", "story", "post", "breaking", "report"],
            api_patterns=["/api/articles", "/wp-json/wp/v2/posts", "/feed", "/rss"],
        )
    ],
    jugnu_settings=JugnuSettings(
        link_confidence_threshold=0.35,
        max_concurrent_crawls=10,
        carry_forward_on_failure=False,
    ),
)
