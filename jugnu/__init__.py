"""Jugnu — self-learning web crawler for domain-specific data extraction.

Public API:
    from jugnu import Jugnu, Skill, Blink, CrawlStatus, CrawlInput, SkillMemory
"""
from __future__ import annotations

from jugnu.contracts import Blink, CrawlInput, CrawlStatus
from jugnu.crawler import Jugnu
from jugnu.skill import Skill
from jugnu.spark.skill_memory import SkillMemory

__all__ = ["Jugnu", "Skill", "Blink", "CrawlStatus", "CrawlInput", "SkillMemory"]
__version__ = "0.1.0"
