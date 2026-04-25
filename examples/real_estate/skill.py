"""Real-estate listing crawler example Skill."""
from __future__ import annotations

from jugnu.skill import JugnuSettings, OutputSchema, Skill, SourceHint

real_estate_skill = Skill(
    name="real_estate_listings",
    version="1.0.0",
    description="Extract property listings including address, price, bedrooms, bathrooms, sqft.",
    output_schema=OutputSchema(
        fields=["address", "price", "bedrooms", "bathrooms", "sqft", "listing_url", "property_type"],
        primary_key="listing_url",
        merging_keys=["address"],
        minimum_fields=["address", "price"],
    ),
    source_hints=[
        SourceHint(
            link_keywords=["listing", "property", "home", "house", "for-sale", "rent", "condo"],
            api_patterns=["/api/listings", "/properties/search", "/v2/homes"],
        )
    ],
    jugnu_settings=JugnuSettings(
        link_confidence_threshold=0.4,
        max_concurrent_crawls=5,
        carry_forward_on_failure=True,
    ),
)
