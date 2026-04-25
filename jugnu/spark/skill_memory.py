from __future__ import annotations

import hashlib
from typing import Optional
from pydantic import BaseModel, Field


class ImprovementSignal(BaseModel):
    signal_type: str
    url: str = ""
    field_name: str = ""
    hint: str = ""
    platform: Optional[str] = None
    confidence: float = 0.5
    prompt_source: str = ""
    raw_context: str = ""
    timestamp: Optional[str] = None


class ConsolidationLogEntry(BaseModel):
    triggered_by: str
    signal_count: int = 0
    signals_processed: int = 0
    memory_version_before: int = 0
    memory_version_after: int = 0
    cost_usd: float = 0.0
    timestamp: Optional[str] = None
    summary: str = ""


class SkillMemory(BaseModel):
    skill_name: str
    skill_version: str
    skill_hash: str
    memory_version: int = 1
    high_confidence_api_patterns: list[str] = []
    high_confidence_link_keywords: list[str] = []
    field_extraction_hints: dict[str, str] = {}
    platform_fingerprints: dict[str, list[str]] = {}
    navigation_wisdom: str = ""
    confirmed_field_synonyms: dict[str, list[str]] = {}
    known_noise_patterns: list[str] = []
    prompt1_context: str = ""
    prompt2_context: str = ""
    prompt4_context: str = ""
    pending_signals: list[ImprovementSignal] = []
    consolidation_log: list[ConsolidationLogEntry] = []
    warmup_cost_usd: float = 0.0
    total_consolidation_cost_usd: float = 0.0

    @classmethod
    def compute_hash(cls, skill_name: str, skill_version: str) -> str:
        return hashlib.sha256(f"{skill_name}::{skill_version}".encode()).hexdigest()[:16]

    @classmethod
    def create_for_skill(cls, skill_name: str, skill_version: str) -> "SkillMemory":
        return cls(
            skill_name=skill_name,
            skill_version=skill_version,
            skill_hash=cls.compute_hash(skill_name, skill_version),
        )

    def is_stale_for(self, skill: object) -> bool:
        expected = self.compute_hash(
            getattr(skill, "name", ""),
            getattr(skill, "version", ""),
        )
        return self.skill_hash != expected

    def add_signal(self, signal: ImprovementSignal) -> None:
        self.pending_signals.append(signal)

    def pending_signal_count(self) -> int:
        return len(self.pending_signals)
