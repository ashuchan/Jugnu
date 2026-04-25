"""Jugnu class — warm_up() and crawl() orchestration API.

Implemented in Phase 10.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from jugnu.contracts import Blink, CrawlInput
    from jugnu.skill import Skill
    from jugnu.spark.skill_memory import SkillMemory


class Jugnu:
    """Self-learning web crawler. One Skill → one SkillMemory → many URLs."""

    def __init__(
        self,
        skill: "Skill",
        skill_memory: Optional["SkillMemory"] = None,
    ) -> None:
        self.skill = skill
        self._skill_memory = skill_memory

    async def warm_up(self) -> "SkillMemory":
        """Run Prompt-5 to initialise SkillMemory. Skipped if valid memory passed in."""
        raise NotImplementedError("Phase 10")

    async def crawl(
        self,
        inputs: "dict[str, CrawlInput]",
    ) -> "dict[str, Blink]":
        """Crawl all URLs concurrently. Returns one Blink per URL."""
        raise NotImplementedError("Phase 10")

    @property
    def skill_memory(self) -> Optional["SkillMemory"]:
        return self._skill_memory
