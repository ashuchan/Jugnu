🪲

**Jugnu**

_Self-Learning Web Crawler - Open Source Library_

**Claude Code Implementation Instructions**

v2.0 · April 2026 · Extracted from PropAi / RealPage MA POC

**Scope:** Extract Jugnu from PropAi as a standalone Python open-source library. Incorporate crawl4ai improvements (litellm, fit-markdown, chunked LLM). Implement SkillMemory as a Skill-level reusable living memory with Prompt-6 self-improvement and batched consolidation with smart triggers. Ship phase-by-phase with PR gates.

**Key corrections in v2.0:** (1) Warmup is Skill-level, not URL-level - fires once at Jugnu instantiation, not per-URL. (2) SkillMemory is a first-class output returned in Blink.llm_profile. (3) SkillMemory self-improves during the crawl via Prompt-6 batched consolidation. (4) profile_storage_path removed - callers own profile persistence.

# **0\. How to Read This Document**

This is the authoritative Claude Code instruction set for building the Jugnu open-source library. Sections are sequential phases. Do not begin Phase N+1 until Phase N's gate passes.

**⚠ AUTHORITY ORDER:** This document overrides all prior memory about PropAi/Jugnu. When this doc and any other source conflict, this doc wins.

| **Phase** | **Name**                            | **Primary Deliverable**                                         |
| --------- | ----------------------------------- | --------------------------------------------------------------- |
| P0        | Repo bootstrap + extraction audit   | New GitHub repo, empty package scaffold, source audit report    |
| P1        | Core contracts + Skill schema       | jugnu/skill.py, jugnu/contracts.py, jugnu/profile.py            |
| P2        | Ember engine (fetch layer)          | jugnu/ember/ - Playwright fetcher, stealth, proxy, rate limiter |
| P3        | Lantern engine (discovery)          | jugnu/lantern/ - link ranker, API ranker, Prompt-1              |
| P4        | Glow engine (extraction cascade)    | jugnu/glow/ - adapter registry, tier cascade, schema normalizer |
| P5        | Spark engine - Warmup + SkillMemory | jugnu/spark/warmup.py, skill_memory.py, Prompt-5                |
| P6        | Spark engine - Extraction prompts   | jugnu/spark/ Prompts 1-4, content_cleaner, crystallizer         |
| P7        | Spark engine - Memory consolidation | jugnu/spark/consolidator.py, Prompt-6, smart trigger            |
| P8        | Profile lifecycle + drift           | jugnu/profile_updater.py, drift_detector.py, cluster_learner.py |
| P9        | Validation + merging                | jugnu/validation/, Prompt-3 merge, cross-run sanity             |
| P10       | crawl() API + Swarm concurrency     | jugnu/crawler.py - crawl(), warm_up(), Swarm, CrawlResult       |
| P11       | Reporting + observability           | jugnu/reporting/, jugnu/observability/                          |
| P12       | Examples + docs + tests             | examples/, tests/, README, API docs                             |
| P13       | PR creation + CI gate               | GitHub PRs per phase, CI workflow, release 0.1.0                |

# **1\. Naming Philosophy - Jugnu as a Firefly**

Jugnu means firefly. Every module is named from the firefly metaphor: emit structured light (data), navigate by signal strength (confidence), adapt the signal to context, and grow brighter with experience.

| **Module / Class** | **Firefly Metaphor**                                     | **What It Does**                                                                        |
| ------------------ | -------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Ember              | The heat source that ignites a firefly                   | Fetch layer: Playwright, stealth, proxy, rate limiter                                   |
| Lantern            | The structure shaping the light                          | Discovery: link ranking, API ranking, confidence scoring                                |
| Glow               | The actual emitted light - the extraction                | Extraction cascade: adapter registry, tier cascade, profile replay                      |
| Spark              | The moment the light first fires - LLM layer             | LLM teacher: litellm provider, all 6 prompts, crystallizer                              |
| Skill              | The firefly's behavioral instinct                        | User input: schema, hints, LLM settings, instructions                                   |
| SkillMemory        | The pattern the firefly remembers across all its flights | Skill-level living memory: domain wisdom, self-improving, returned in Blink.llm_profile |
| Blink              | A single flash - one URL's complete result               | Per-URL crawl result: data, status, scrape_profile, llm_profile                         |
| Swarm              | Many fireflies coordinating                              | Concurrency: AsyncPool, semaphore, resource-based sizing                                |
| Drift              | A firefly blown off course                               | Drift detection: profile demotion triggers, re-teaching                                 |
| Cluster            | Fireflies sharing a signal pattern                       | Cross-URL platform learning: shared profiles across similar sites                       |
| Trace              | The path a firefly has flown                             | Observability: structured event ledger, cost ledger                                     |

# **2\. The Skill File - Domain-Specific Crawl Instructions**

A Skill is the primary user-facing input to Jugnu. It describes what to extract, from where, in what structure, and how aggressively to use LLM. PMS adapters (RentCafe, Entrata) in PropAi were domain-specific adapter knowledge encoded in Python. The Skill generalizes this - domain knowledge is expressed as data, not code.

## **2.1 Full Skill Schema (jugnu/skill.py)**

from pydantic import BaseModel, Field

from typing import Optional, Literal

class LiteLLMSettings(BaseModel):

"""LiteLLM provider config. Field names passed as-is to litellm.completion().

Supports any litellm provider: openai/gpt-4o, anthropic/claude-3-haiku,

ollama/llama3, groq/llama3-70b, azure/gpt-4o-mini, etc."""

model: str = "openai/gpt-4o-mini"

api_key: Optional\[str\] = None # reads from env if None

api_base: Optional\[str\] = None # for self-hosted / Azure endpoints

temperature: float = 0.0 # 0.0 = deterministic, required for consistent mappings

max_tokens: int = 4096

timeout: int = 60

extra_kwargs: dict = Field(default_factory=dict) # passed through to litellm verbatim

class VisionLLMSettings(LiteLLMSettings):

"""Vision tasks (screenshot analysis, Tier-5 fallback). Needs multimodal model."""

model: str = "openai/gpt-4o"

class OutputSchema(BaseModel):

"""Defines the canonical output shape Jugnu must produce.

Think of this as the domain record definition.

Real estate example: fields=\[unit_id, rent, bedrooms, availability_date\]

Finance example: fields=\[ticker, price, volume, market_cap\]"""

fields: list\[str\] # all extractable field names

primary_key: Optional\[str\] = None # if set, Jugnu generates sha256 key for new records

merging_keys: list\[str\] = \[\] # fields to match new records to prior-run records

minimum_fields: list\[str\] # must be non-null for a record to count as success

json_schema: dict = Field(default_factory=dict) # optional JSON Schema for strict validation

class SourceHint(BaseModel):

"""Typed hint about where data lives. Generalizes the PropAi PMS adapter concept.

PropAi had code adapters for RentCafe/Entrata. SourceHint expresses the same

knowledge as data - portable, LLM-readable, no Python required."""

platform: Optional\[str\] = None # known platform: 'rentcafe', 'shopify', 'yahoo_finance'

api_patterns: list\[str\] = \[\] # URL substrings that typically contain target data

link_keywords: list\[str\] = \[\] # anchor text/path keywords to prioritize

dom_selectors: dict\[str, str\] = {} # CSS selectors for known DOM field locations

class ScreenshotSettings(BaseModel):

"""Controls screenshot capture. Screenshots serve two purposes:

(1) audit trail for compliance, (2) Vision LLM fallback input."""

enabled: bool = False

on_success: bool = False # capture even when extraction succeeded

on_failure: bool = True # always capture on extraction failure

on_llm_tier: bool = True # capture before sending to Vision LLM

format: Literal\["png","jpeg"\] = "jpeg"

quality: int = 80

full_page: bool = True

class JugnuSettings(BaseModel):

"""Global crawler behavior. Controls cost thresholds, depth limits, cascade behavior,

and SkillMemory consolidation triggers."""

link_confidence_threshold: float = 0.4

\# ^ min confidence to follow a link/API. Lower = more exploration (more LLM cost).

max_external_depth: int = 0

\# ^ hops to follow external links. 0 = stay on input URL only.

max_llm_calls_per_url: int = 3

\# ^ hard cap on LLM calls per URL per run. Prevents runaway cost.

max_concurrent_crawls: int = 0

\# ^ 0 = auto-detect from RAM/CPU. Otherwise explicit concurrency.

carry_forward_on_failure: bool = True

\# ^ emit last successful data with CARRIED_FORWARD flag on fetch failure.

memory_consolidation_batch_size: int = 50

\# ^ how many URLs to process before running Prompt-6 memory consolidation.

\# Lower = faster learning, more LLM cost. Higher = slower learning, cheaper.

memory_consolidation_smart_trigger_count: int = 3

\# ^ trigger immediate consolidation when a new platform pattern is confirmed

\# this many times within the current pending signals batch.

\# Ensures the fleet benefits from a new discovery without waiting for full batch.

class Skill(BaseModel):

"""The Skill is the primary user input to Jugnu. Encodes everything about

WHAT to extract and WHERE to look for it across all target URLs.

One Skill → one SkillMemory → all URLs in the crawl batch.

Example domains:

\- Real estate: apartment availability + rent from property websites

\- Finance: stock prices + fundamentals from financial data sites

\- Sports: match scores + standings from sports aggregators

\- News: headlines + summaries from news publishers"""

name: str # human-readable, used as SkillMemory cache key

version: str = '1.0' # increment when instructions change → invalidates SkillMemory

description: str

output_schema: OutputSchema

general_instructions: str

\# ^ natural language extraction goal with real-world examples.

\# Fed directly into all LLM prompts. Be specific. Include field examples.

source_hints: list\[SourceHint\] = \[\]

\# ^ known platforms / URL patterns. Empty = fully exploratory (more LLM cost).

llm: LiteLLMSettings = Field(default_factory=LiteLLMSettings)

vision_llm: VisionLLMSettings = Field(default_factory=VisionLLMSettings)

screenshot: ScreenshotSettings = Field(default_factory=ScreenshotSettings)

settings: JugnuSettings = Field(default_factory=JugnuSettings)

# **3\. SkillMemory - The Living Domain Brain**

SkillMemory is Jugnu's most important architectural innovation. It is a Skill-level reusable memory - not URL-level, not run-level. It is produced once at Jugnu instantiation (Prompt-5 Warmup), carried across all URLs in the crawl batch, self-improves via Prompt-6 consolidation as the batch progresses, and is returned in every Blink.llm_profile so the caller can persist it and reuse it on the next run.

**Critical distinction:** SkillMemory answers 'what does this DOMAIN look like?' ScrapeProfile answers 'what does THIS URL look like?' They are different objects, stored and managed separately. SkillMemory belongs to the Skill. ScrapeProfile belongs to a URL.

## **3.1 SkillMemory Schema (jugnu/spark/skill_memory.py)**

from pydantic import BaseModel, Field

from datetime import datetime

from typing import Optional

import hashlib, json

class ImprovementSignal(BaseModel):

"""Evidence collected from one URL's prompt responses.

Every Prompt-1/2/4 response includes an improvement_signal key.

Accumulated in SkillMemory.pending_signals until consolidation fires."""

url: str

prompt_stage: str # 'discovery' | 'extraction' | 'external_rank'

succeeded: bool

tier_used: Optional\[str\] = None

platform_observed: Optional\[str\] = None

api_patterns_that_worked: list\[str\] = \[\]

api_patterns_that_failed: list\[str\] = \[\]

json_paths_that_worked: dict\[str,str\] = {} # field_name → \$.json.path

dom_selectors_that_worked: dict\[str,str\] = {}

field_synonyms_discovered: dict\[str,list\[str\]\] = {} # canonical → \[site-specific names\]

misleading_patterns: list\[str\] = \[\] # looked promising, had no data

free_text_observation: str = '' # LLM's own words about what it learned

class ConsolidationLogEntry(BaseModel):

"""Audit record of one Prompt-6 consolidation run."""

memory_version: int

consolidated_at: datetime

urls_in_batch: int

signals_merged: int

trigger: str # 'batch_size' | 'smart_trigger' | 'run_end'

key_changes: list\[str\] # human-readable bullets of what changed

cost_usd: float

tokens_in: int

tokens_out: int

class SkillMemory(BaseModel):

"""Skill-level reusable domain wisdom. One instance per Jugnu instantiation.

Shared across all URLs in the batch. Self-improves via Prompt-6.

Returned in every Blink.llm_profile - caller persists and reuses across runs.

Cache key: skill_hash. Stale if skill.name+skill.version changes.

Lifecycle:

1\. Jugnu(skill=...) → warm_up() → SkillMemory v1 (Prompt-5, pure LLM, no page load)

2\. crawl() processes URLs → pending_signals accumulates per-URL evidence

3\. Every N URLs (or smart trigger) → Prompt-6 → SkillMemory v2, v3, ...

4\. crawl() returns → blink.llm_profile = final SkillMemory

5\. Next run: Jugnu(skill=..., skill_memory=persisted) → warm_up() skipped"""

\# Identity

skill_name: str

skill_version: str

skill_hash: str # sha256(skill.name + '::' + skill.version)

created_at: datetime = Field(default_factory=datetime.utcnow)

\# Version tracking

memory_version: int = 1 # increments on each Prompt-6 consolidation

total_urls_learned_from: int = 0 # running total across all runs

consolidation_log: list\[ConsolidationLogEntry\] = \[\]

\# ── Domain knowledge (populated by Prompt-5, improved by Prompt-6) ──────

high_confidence_api_patterns: list\[str\] = \[\]

\# e.g. \['/api/getApartments', '/availability', '/floorplans'\]

high_confidence_link_keywords: list\[str\] = \[\]

\# e.g. \['floor-plans', 'availability', 'apartments'\]

field_extraction_hints: dict\[str,str\] = {}

\# field_name → hint string. e.g. {'rent_low': 'Look for monthlyRent or rentAmount'}

platform_fingerprints: dict\[str,list\[str\]\] = {}

\# platform_name → \[url_patterns\]. Detected from source_hints + learned from signals

navigation_wisdom: str = ''

\# General navigation notes for this domain. Updated by Prompt-6.

confirmed_field_synonyms: dict\[str,list\[str\]\] = {}

\# canonical_field → \[site-specific names seen across URLs\]

\# e.g. {'rent_low': \['monthlyRent','rentAmount','listPrice','askingRent'\]}

known_noise_patterns: list\[str\] = \[\]

\# URL patterns / DOM selectors confirmed to contain NO useful data

\# ── Pre-generated prompt context fragments ──────────────────────────────

\# Injected verbatim into downstream prompts. Regenerated by Prompt-6.

prompt1_context: str = '' # injected into every Prompt-1 (discovery)

prompt2_context: str = '' # injected into every Prompt-2 (extraction)

prompt4_context: str = '' # injected into every Prompt-4 (external rank)

\# ── Pending signals (cleared after each consolidation) ──────────────────

pending_signals: list\[ImprovementSignal\] = \[\]

\# ── Cost accounting ─────────────────────────────────────────────────────

warmup_cost_usd: float = 0.0 # Prompt-5 cost (paid once)

total_consolidation_cost_usd: float = 0.0 # cumulative Prompt-6 cost

@classmethod

def compute_hash(cls, skill_name: str, skill_version: str) -> str:

return hashlib.sha256(f'{skill_name}::{skill_version}'.encode()).hexdigest()\[:16\]

def is_stale_for(self, skill: 'Skill') -> bool:

'''Returns True if skill changed since this memory was created.',

' Stale memory triggers automatic re-warmup.'''

return self.skill_hash != self.compute_hash(skill.name, skill.version)

# **4\. The Six Prompt Architecture**

Jugnu uses six distinct LLM prompt stages. Prompts 1-4 fire per-URL. Prompt-5 (Warmup) fires once at instantiation. Prompt-6 (Memory Consolidation) fires periodically during the crawl batch. All prompts are generated at runtime from templates in jugnu/spark/prompts/ - never hard-coded.

**Improvement signal rule:** Prompts 1, 2, and 4 MUST return an improvement_signal key alongside their primary output. This is how the fleet teaches SkillMemory. A prompt response without improvement_signal is treated as malformed and retried.

| **Prompt**               | **Stage**                  | **Fires When**                                                              |
| ------------------------ | -------------------------- | --------------------------------------------------------------------------- |
| Prompt-5 (Warmup)        | Skill-level - once at init | Jugnu.warm_up() called; skipped if valid SkillMemory passed in              |
| Prompt-1 (Discovery)     | Per-URL - link/API ranking | After page renders + XHR captured; deterministic ranking is below threshold |
| Prompt-2 (Extraction)    | Per-URL - data extraction  | When a source cannot be parsed deterministically                            |
| Prompt-3 (Merge)         | Per-URL - record matching  | When CrawlInput.previous_records is provided AND new records extracted      |
| Prompt-4 (External)      | Per-URL - last resort      | When internal sources exhausted AND max_external_depth > 0                  |
| Prompt-6 (Consolidation) | Skill-level - batched      | Every N URLs completed; or smart trigger; or run end                        |

## **Prompt-5: Warmup - Skill Analysis (no page load)**

### **What it is**

A pure LLM call against the Skill definition itself. No URL is visited. No page is loaded. Prompt-5 asks the LLM to synthesize domain-level extraction wisdom from the Skill's instructions, schema, and source hints. This is fundamentally different from Prompts 1-4 which require live pages.

### **When it fires**

Once per Jugnu instance lifecycle - inside warm_up() which is called either explicitly before crawl() or lazily on the first crawl() invocation. If the caller passes a valid SkillMemory (matching skill_hash) at instantiation, warmup is skipped entirely.

### **Inputs**

- skill.general_instructions
- skill.output_schema - all fields, minimum_fields, field descriptions
- skill.source_hints - platform names, api_patterns, link_keywords
- No URL, no page content, no DOM - pure Skill analysis

### **Output: initial SkillMemory**

{

"high_confidence_api_patterns": \["/api/getApartments","/availability","/floorplans"\],

"high_confidence_link_keywords": \["floor-plans","availability","apartments"\],

"field_extraction_hints": {

"rent_low": "Look for monthlyRent, rentAmount, price in JSON or .price-amount in DOM",

"bedrooms": "beds, bedroomCount, br in JSON or .beds-label, .bed-count in DOM"

},

"platform_fingerprints": {

"rentcafe": \["/api/getApartments","default.aspx","/GetApartmentsByFilter"\],

"entrata": \["/api/v1/properties","/module/widgets/"\],

"appfolio": \["/api/available_rentals"\]

},

"navigation_wisdom": "Most apartment sites load unit data on pages labeled Floor Plans or Availability. Many use XHR - watch for API calls on page load before clicking anything.",

"prompt1_context": "...\[generated context fragment for Prompt-1\]...",

"prompt2_context": "...\[generated context fragment for Prompt-2\]...",

"prompt4_context": "...\[generated context fragment for Prompt-4\]..."

}

## **Prompt-1: Discovery - Link & API Ranker**

### **When it fires**

After the page renders and XHR/fetch calls are captured. Deterministic ranking (using SkillMemory.high_confidence_api_patterns and link_keywords) runs first - Prompt-1 fires only if no candidate scores above settings.link_confidence_threshold deterministically.

### **Inputs**

- Captured XHR/fetch API calls (URL, content-type, body size)
- Internal hyperlinks (anchor text + href)
- SkillMemory.prompt1_context - injected verbatim (grows richer each consolidation)
- skill.output_schema.minimum_fields - what MUST be found

### **Output**

{

"ranked_apis": \[{ "url":"...", "confidence":0.92, "reason":"..." }\],

"ranked_links": \[{ "href":"...", "confidence":0.75, "reason":"..." }\],

"platform_guess": "rentcafe",

"navigation_hint": "Click the Availability tab before scraping.",

"improvement_signal": {

"prompt_stage": "discovery",

"platform_observed": "rentcafe",

"api_patterns_that_worked": \[\],

"misleading_patterns": \["/api/v1/chat/config"\],

"free_text_observation": "Chat config API always appears but contains no unit data."

}

}

## **Prompt-2: Extraction - Data Teacher**

### **When it fires**

When a ranked source (API or DOM section) cannot be parsed deterministically. Applies fit_markdown pre-processing first. Chunks if content exceeds max_tokens \* 0.7. The LLM extracts data AND returns field_mappings for deterministic replay on future runs.

### **Key requirement: fit_markdown before LLM**

Raw HTML is NEVER sent to Prompt-2. Always run html_to_fit_markdown() first. This reduces input tokens 50-80% by stripping nav, footer, scripts, ads - keeping only content-bearing HTML, converted to Markdown.

### **Output**

{

"records": \[{ "unit_id":"A101","rent_low":2450,"bedrooms":2,"confidence":0.91 }\],

"field_mappings": {

"api": { "url_pattern":"/api/getApartments", "json_paths":{"rent_low":"\$.data\[\*\].monthlyRent"}, "response_envelope":"data" },

"dom": { "container":".unit-card", "rent_low":".unit-price span", "bedrooms":".beds-count" }

},

"platform_confirmed": "rentcafe",

"field_mapping_notes": "monthlyRent is pre-concession price. effectiveRent includes concessions.",

"improvement_signal": {

"prompt_stage": "extraction",

"succeeded": true,

"tier_used": "TIER_4_LLM_API",

"api_patterns_that_worked": \["/api/getApartments"\],

"json_paths_that_worked": { "rent_low":"\$.data\[\*\].monthlyRent","bedrooms":"\$.data\[\*\].beds" },

"field_synonyms_discovered": { "rent_low":\["monthlyRent"\],"bedrooms":\["beds"\] },

"free_text_observation": "RentCafe always uses monthlyRent for the base price."

}

}

## **Prompt-3: Merge - Record Matching**

### **When it fires**

When CrawlInput.previous_records is non-empty AND new records were extracted this run. Determines which new records map to existing ones (update) vs. which are genuinely new (insert).

### **Output**

{

"merge_decisions": \[

{ "new_record_index":0, "existing_record_id":"unit_A101", "merge":true, "reason":"unit_id match" },

{ "new_record_index":1, "existing_record_id":null, "merge":false, "reason":"New listing" }

\]

}

// Note: Prompt-3 does NOT return improvement_signal - merge decisions are not domain learning.

## **Prompt-4: External Ranker - Last Resort**

### **When it fires**

Only when settings.max_external_depth > 0 AND all internal sources exhausted AND minimum_fields threshold not met. Ranks external links by probability of containing the missing fields.

### **Output**

{

"ranked_external_links": \[

{ "url":"<https://external.com/listings>", "confidence":0.71, "reason":"...", "depth":1 }

\],

"improvement_signal": {

"prompt_stage": "external_rank",

"succeeded": false,

"misleading_patterns": \["<https://ads.example.com"\>],

"free_text_observation": "Ads domains consistently rank high but contain no data."

}

}

## **Prompt-6: Memory Consolidation - Self-Improvement**

### **What it is**

The engine that makes SkillMemory a living document. Prompt-6 takes accumulated ImprovementSignals from the last N URLs and merges them into the existing SkillMemory. It promotes confirmed patterns, demotes noise, extends field synonyms, and regenerates the prompt context fragments that all other prompts use. After consolidation, the remaining URLs in the batch get measurably better prompts.

### **Trigger conditions - all checked after each URL completes**

- Batch trigger: len(skill_memory.pending_signals) >= settings.memory_consolidation_batch_size (default 50)
- Smart trigger: a new platform pattern appears in pending_signals >= settings.memory_consolidation_smart_trigger_count times (default 3). This fires immediately so the remaining fleet benefits from the discovery without waiting for the full batch.
- Run-end trigger: crawl() finishes - consolidate remaining pending_signals regardless of count. This ensures the returned SkillMemory reflects all evidence from the run.

### **Why batched (not per-URL)**

Consolidating after every URL would cost one LLM call per URL - negating cost savings. The batch approach costs 1 consolidation per N URLs. At 5000 URLs and batch_size=50: 100 consolidation calls vs. 5000 per-URL calls. The signal quality also improves with batch size - a single URL's signal could be noise; 50 URLs confirming the same pattern is evidence.

### **Smart trigger mechanics**

\# Inside Swarm after each Blink completes:

async def \_maybe_consolidate(skill_memory: SkillMemory, spark: SparkEngine, settings: JugnuSettings):

signals = skill_memory.pending_signals

\# Batch trigger

if len(signals) >= settings.memory_consolidation_batch_size:

await consolidate(skill_memory, spark, trigger='batch_size')

return

\# Smart trigger: count new platform confirmations

platform_counts: dict\[str,int\] = {}

for sig in signals:

if sig.platform_observed:

known = skill_memory.platform_fingerprints.get(sig.platform_observed, \[\])

if not known: # platform not yet in SkillMemory

platform_counts\[sig.platform_observed\] = platform_counts.get(sig.platform_observed, 0) + 1

for platform, count in platform_counts.items():

if count >= settings.memory_consolidation_smart_trigger_count:

await consolidate(skill_memory, spark, trigger='smart_trigger')

return

\# At end of crawl():

if skill_memory.pending_signals:

await consolidate(skill_memory, spark, trigger='run_end')

### **What Prompt-6 improves**

- high_confidence_api_patterns - promoted when appearing in multiple succeeded signals
- confirmed_field_synonyms - extended with newly discovered field name mappings
- known_noise_patterns - extended with URLs that appeared in misleading_patterns
- platform_fingerprints - new platforms added when confirmed by smart trigger
- field_extraction_hints - refined with specific JSON paths that worked at scale
- prompt1_context, prompt2_context, prompt4_context - regenerated to reflect all improvements
- navigation_wisdom - updated with domain-level navigation observations

### **The compound effect**

By URL #500 in a 5000-URL batch (10 consolidations): confirmed_field_synonyms maps monthlyRent, rentAmount, listPrice, askingRent all to rent_low. known_noise_patterns has 30+ chat/analytics endpoints. Prompt-2 succeeds on first attempt for >80% of sites. By URL #5000 (100 consolidations): SkillMemory is a distilled encyclopedia of this domain's extraction patterns.

# **5\. Public API - Jugnu Class and Blink Output**

## **5.1 Jugnu Class (jugnu/crawler.py)**

class Jugnu:

def \__init_\_(

self,

skill: Skill,

skill_memory: Optional\[SkillMemory\] = None,

\# ^ Pass persisted SkillMemory from a prior run to skip warmup.

\# If None OR stale (skill hash mismatch) → warm_up() will run automatically.

): ...

async def warm_up(self) -> SkillMemory:

"""Run Prompt-5 to initialize SkillMemory from the Skill definition.

Call explicitly before crawl() for eager initialization,

or let crawl() call it lazily on first invocation.

Returns the SkillMemory so caller can inspect warmup cost before crawling.

Idempotent - if already warmed up with a valid (non-stale) memory, returns it.

"""

if self.\_skill_memory and not self.\_skill_memory.is_stale_for(self.skill):

return self.\_skill_memory # already warm - skip

self.\_skill_memory = await run_warmup(self.skill, self.\_spark)

return self.\_skill_memory

async def crawl(

self,

inputs: dict\[str, CrawlInput\],

\# ^ key = URL string

\# ^ value = CrawlInput(scrape_profile, previous_records)

\# scrape_profile: None on first visit; returned ScrapeProfile on subsequent runs

\# previous_records: None on first visit; prior Blink.records for merge mode

) -> dict\[str, Blink\]:

"""Crawl all URLs concurrently. Returns one Blink per URL.

Every Blink contains blink.llm_profile = the current SkillMemory (same object

across all Blinks in this run - includes all consolidations up to run-end).

"""

if not self.\_skill_memory or self.\_skill_memory.is_stale_for(self.skill):

await self.warm_up() # lazy init

...

\# SkillMemory is updated in-place during the run via consolidate()

\# Run-end consolidation fires here before return

return {url: blink for url, blink in results.items()}

## **5.2 CrawlInput and Blink**

@dataclass

class CrawlInput:

scrape_profile: Optional\[ScrapeProfile\]

\# ^ Per-URL learned profile. None on first visit.

\# Pass the ScrapeProfile from the prior run's Blink on subsequent crawls.

\# Jugnu does NOT persist profiles internally - caller owns persistence.

previous_records: Optional\[list\[dict\]\]

\# ^ Records from prior run for merge mode (Prompt-3). None = no merge.

@dataclass

class Blink:

\# Identity

url: str

status: CrawlStatus # SUCCESS | PARTIAL | FAILED | CARRIED_FORWARD | PARKED | SKIP

\# Data

records: list\[dict\] # validated records matching OutputSchema

\# Profiles - caller persists both for next run

scrape_profile: ScrapeProfile

\# ^ URL-specific learned profile: winning endpoint, field mappings, maturity

llm_profile: SkillMemory

\# ^ Skill-level living memory: SAME OBJECT on every Blink in this run.

\# Reflects all consolidations that occurred during the crawl.

\# Pass back to Jugnu(skill_memory=blink.llm_profile) on next run → no warmup cost.

\# Extraction metadata

tier_used: str # e.g. 'TIER_1_PROFILE_MAPPING', 'TIER_4_LLM_API'

confidence: float

carry_forward_days: int

\# Cost - URL-level only; warmup + consolidation costs are in llm_profile

llm_cost_usd: float

llm_interactions: list\[dict\] # full call log for audit

\# Reports

report_md: str

screenshots: list\[bytes\] # empty if screenshot.enabled=False

errors: list\[str\]

## **5.3 Caller Run Loop - How to Persist Between Runs**

\# ── First run ─────────────────────────────────────────────────────────────

jugnu = Jugnu(skill=REAL_ESTATE_SKILL) # no cached memory

await jugnu.warm_up() # optional: eager warmup

print(f'Warmup cost: \${jugnu.skill_memory.warmup_cost_usd:.4f}')

results = await jugnu.crawl({

url: CrawlInput(scrape_profile=None, previous_records=None)

for url in my_url_list

})

\# Persist after first run

any_blink = next(iter(results.values()))

my_store.save_skill_memory(REAL_ESTATE_SKILL.name, any_blink.llm_profile) # one per Skill

for url, blink in results.items():

my_store.save_scrape_profile(url, blink.scrape_profile) # one per URL

my_store.save_records(url, blink.records)

\# ── Subsequent runs (daily) ────────────────────────────────────────────────

cached_memory = my_store.load_skill_memory(REAL_ESTATE_SKILL.name)

jugnu = Jugnu(skill=REAL_ESTATE_SKILL, skill_memory=cached_memory) # warmup skipped

results = await jugnu.crawl({

url: CrawlInput(

scrape_profile=my_store.load_scrape_profile(url), # URL-specific profile

previous_records=my_store.load_records(url), # for Prompt-3 merge

)

for url in my_url_list

})

\# SkillMemory continues improving from where last run left off

my_store.save_skill_memory(REAL_ESTATE_SKILL.name, any_blink.llm_profile)

# **6\. Library Architecture**

## **6.1 Repository Structure**

jugnu/

├── \__init_\_.py # Public API: Jugnu, Skill, Blink, CrawlStatus, SkillMemory

├── skill.py # Skill, OutputSchema, SourceHint, LiteLLMSettings, JugnuSettings

├── contracts.py # Blink, CrawlStatus, CrawlInput, FetchResult, AdapterResult

├── crawler.py # Jugnu class - warm_up(), crawl(), Swarm orchestration

├── profile.py # ScrapeProfile, ProfileMaturity, LlmFieldMapping, etc.

├── profile_store.py # ProfileStore utility - load/save/bootstrap (caller-optional)

├── profile_updater.py # update_after_blink() - maturity, mappings, streaks

├── drift_detector.py # detect_drift(), apply_demotion()

├── cluster_learner.py # find_cluster(), bootstrap_from_cluster()

├── dlq.py # Dead-letter queue - parking, retry cadence

│

├── ember/ # Fetch layer (firefly ignition)

│ ├── fetcher.py # fetch() - FetchTask → FetchResult, never raises

│ ├── stealth.py # IdentityPool - 8 identities, SHA256-mapped per URL

│ ├── proxy_pool.py # ProxyPool - health ±0.05/±0.25, quarantine <0.25

│ ├── rate_limiter.py # PerHostTokenBucket - 2 req/s default

│ ├── captcha_detect.py # looks_like_captcha()

│ └── change_detector.py # RenderMode: HOT+<1day → GET, else RENDER

│

├── lantern/ # Discovery layer (shaping the light)

│ ├── link_extractor.py # extract_links_and_apis() from DOM + network log

│ ├── link_ranker.py # rank_deterministic() - uses SkillMemory patterns

│ ├── api_heuristics.py # looks_like_data_api(), response_has_records()

│ └── discovery_prompt.py # build_prompt1() - Prompt-1 text generation

│

├── glow/ # Extraction layer (emitting light)

│ ├── adapter_registry.py # AdapterRegistry - get_adapter(), register()

│ ├── base_adapter.py # GlowAdapter Protocol + AdapterContext

│ ├── generic_adapter.py # GlowGenericAdapter - full tier cascade

│ ├── platform_detector.py # detect_platform() - offline + body-shape confirm

│ ├── resolver.py # resolve_target() - CTA hop, iframe, redirect

│ ├── schema_normalizer.py # raw fields → OutputSchema + SkillMemory synonyms

│ └── tiers/

│ ├── tier1_profile.py # Profile mapping replay (zero LLM)

│ ├── tier1_api.py # Known API heuristic parse

│ ├── tier1_embedded.py # \__NEXT_DATA_\_, \__NUXT_\_, SSR blobs

│ ├── tier2_jsonld.py # JSON-LD schema.org

│ ├── tier3_dom.py # CSS selector DOM parse

│ └── tier5_vision.py # Vision LLM screenshot fallback

│

├── spark/ # LLM teacher layer (the first flash)

│ ├── provider.py # SparkProvider - litellm wrapper, logs every call

│ ├── skill_memory.py # SkillMemory, ImprovementSignal, ConsolidationLogEntry

│ ├── content_cleaner.py # html_to_fit_markdown(), chunk_content()

│ ├── warmup.py # run_warmup() - Prompt-5, pure Skill analysis

│ ├── discovery_llm.py # rank_with_llm() - Prompt-1

│ ├── extraction_llm.py # extract_with_llm() - Prompt-2, chunked

│ ├── merge_llm.py # merge_with_llm() - Prompt-3

│ ├── external_ranker_llm.py # rank_external_with_llm() - Prompt-4

│ ├── consolidator.py # consolidate() - Prompt-6, smart trigger check

│ ├── crystallizer.py # profile_crystallizer() - field_mappings → ScrapeProfile

│ └── prompts/

│ ├── warmup.txt # Prompt-5 template

│ ├── discovery.txt # Prompt-1 template

│ ├── extraction.txt # Prompt-2 template

│ ├── merge.txt # Prompt-3 template

│ ├── external_rank.txt # Prompt-4 template

│ └── consolidation.txt # Prompt-6 template

│

├── validation/

│ ├── schema_gate.py # record_is_substantive(), batch_passes_gate()

│ ├── identity_fallback.py # compute_primary_key() - SHA256 composite

│ └── cross_run_sanity.py # detect_value_swings() on any numeric fields

│

├── reporting/

│ ├── blink_report.py # Per-URL markdown report

│ ├── run_report.py # Run-wide summary

│ └── llm_cost_report.py # Per-prompt-stage cost breakdown

│

└── observability/

├── trace.py # emit(), TraceEvent, EventKind - never raises

└── cost_ledger.py # SQLite per-URL, per-prompt-stage cost

examples/

├── real_estate/ ├── finance/ ├── sports/ └── news/

├── skill.py └── run.py

tests/

├── test_skill.py ├── test_skill_memory.py ├── test_ember/

├── test_lantern/ ├── test_glow/ ├── test_spark/ ├── test_validation/

└── fixtures/ ├── real_estate/ ├── finance/ └── sports/

# **7\. Prompt Template Specifications**

All templates live in jugnu/spark/prompts/. Variables in {curly_braces} are filled at runtime by the Spark engine. Claude Code must implement these exact files.

## **7.1 warmup.txt - Prompt-5 (Skill Analysis)**

You are Jugnu, a self-learning web scraper. You are analyzing an extraction Skill definition

to build reusable domain wisdom that will guide all scraping in this domain.

You are NOT visiting any website. You are reasoning about the domain from the Skill alone.

\## Extraction goal

{general_instructions}

\## Output schema

All fields: {output_fields}

Minimum required fields: {minimum_fields}

\## Known source patterns

{source_hints_json}

Based on this Skill, synthesize domain-level wisdom:

1\. What API URL patterns typically expose this kind of data?

2\. What link keywords lead to pages with this data?

3\. For each output field, what are common JSON key names and DOM selectors?

4\. What platforms typically serve this domain? What fingerprints identify them?

5\. What navigation patterns are common? (tabs, lazy loading, pagination)

6\. Generate prompt1_context: a dense paragraph injected into every discovery prompt

7\. Generate prompt2_context: a dense paragraph injected into every extraction prompt

8\. Generate prompt4_context: a dense paragraph injected into every external rank prompt

Respond with JSON only (no markdown, no backticks):

{ high_confidence_api_patterns, high_confidence_link_keywords, field_extraction_hints,

platform_fingerprints, navigation_wisdom, confirmed_field_synonyms,

prompt1_context, prompt2_context, prompt4_context }

## **7.2 discovery.txt - Prompt-1**

You are Jugnu. Rank these discovered links and APIs by likelihood of containing target data.

\## Domain expertise

{skill_memory_prompt1_context}

\## What I need (minimum required: {minimum_fields})

{general_instructions}

\## Captured API calls

{api_candidates_json}

\## Internal hyperlinks

{link_candidates_json}

APIs are generally better sources than HTML links for structured data.

Penalize any URL matching these known noise patterns: {known_noise_patterns}

Respond with JSON only:

{ ranked_apis: \[{url, confidence, reason}\], ranked_links: \[{href, confidence, reason}\],

platform_guess, navigation_hint,

improvement_signal: { prompt_stage:'discovery', platform_observed, api_patterns_that_worked,

api_patterns_that_failed, misleading_patterns, free_text_observation } }

## **7.3 extraction.txt - Prompt-2**

You are Jugnu. Extract structured records from the content below.

CRITICAL: Also return the field_mappings (JSON paths or CSS selectors) so future

extractions can be done deterministically without calling you again.

\## Domain expertise

{skill_memory_prompt2_context}

\## Extraction goal

{general_instructions}

\## Output schema

{output_schema_json}

\## Minimum fields (these MUST be non-null for success)

{minimum_fields}

\## Known field synonyms (use these to find fields by alternate names)

{confirmed_field_synonyms_json}

\## Source: {source_url} | Type: {content_type}

\## Content (fit_markdown preprocessed)

{content}

Respond with JSON only:

{ records: \[{...fields, confidence}\],

field_mappings: { api: {url_pattern, json_paths, response_envelope}, dom: {container, ...selectors} },

platform_confirmed, field_mapping_notes,

improvement_signal: { prompt_stage:'extraction', succeeded, tier_used,

api_patterns_that_worked, json_paths_that_worked, dom_selectors_that_worked,

field_synonyms_discovered, free_text_observation } }

## **7.4 merge.txt - Prompt-3**

You are Jugnu. Match new records to existing records from a prior crawl.

\## Merging keys (primary match criteria): {merging_keys}

\## Domain context: {general_instructions}

\## New records

{new_records_json}

\## Existing records from prior run

{existing_records_json}

Respond with JSON only:

{ merge_decisions: \[{new_record_index, existing_record_id, merge, reason}\] }

## **7.5 external_rank.txt - Prompt-4**

You are Jugnu. You have exhausted internal sources. You may follow external links.

\## Domain expertise

{skill_memory_prompt4_context}

\## Still missing: {missing_fields}

\## Already extracted: {extracted_summary}

\## Depth: {current_depth} of {max_depth}

\## External links

{external_links_json}

Only rank above 0.6 if genuinely likely to have MISSING fields. Be conservative.

Respond with JSON only:

{ ranked_external_links: \[{url, confidence, reason, depth}\],

improvement_signal: { prompt_stage:'external_rank', succeeded, misleading_patterns,

free_text_observation } }

## **7.6 consolidation.txt - Prompt-6 (Memory Consolidation)**

You are Jugnu's domain knowledge curator. Improve the SkillMemory based on evidence

from recent crawls. The SkillMemory is a living document - make it smarter.

\## Current SkillMemory (version {memory_version}, learned from {total_urls} URLs so far)

{current_skill_memory_json}

\## Evidence from the last {batch_size} URLs

{improvement_signals_json}

\## Batch statistics

\- Succeeded: {success_count}/{batch_size}

\- Trigger: {trigger} (batch_size | smart_trigger | run_end)

\- Top tiers used: {tier_distribution}

\- Platforms observed: {platforms_seen}

\## Instructions - update each field of SkillMemory:

1\. high_confidence_api_patterns: promote patterns from multiple succeeded signals

2\. confirmed_field_synonyms: add newly discovered synonyms; merge duplicates

3\. known_noise_patterns: add patterns from misleading_patterns with 2+ confirmations

4\. platform_fingerprints: add newly confirmed platforms (smart_trigger fires for this)

5\. field_extraction_hints: refine with specific JSON paths that worked at scale

6\. navigation_wisdom: update with new domain-level navigation observations

7\. prompt1_context: regenerate - make it more precise and useful for next batch

8\. prompt2_context: regenerate - include top-confirmed JSON paths and synonyms

9\. prompt4_context: regenerate - include confirmed noise patterns to avoid

Return the COMPLETE updated SkillMemory as JSON plus:

improvement_log_entry: { memory_version (incremented), urls_in_batch,

signals_merged, trigger, key_changes: \['bullet 1', 'bullet 2', ...\] }

Respond with JSON only (no markdown, no backticks).

# **8\. Phased Implementation Instructions for Claude Code**

**Hard rule:** Do not begin Phase N+1 until Phase N's gate passes. Each gate is a list of explicit checks below.

## **Phase 0 - Repo Bootstrap + Source Audit**

- Create GitHub repo: github.com/{org}/jugnu. Init: pyproject.toml, README.md, LICENSE (Apache 2.0), .gitignore, .github/workflows/ci.yml
- Create the full directory scaffold from Section 6.1 - all files as empty stubs with module docstrings
- Produce docs/SOURCE_AUDIT.md mapping every PropAi file to its Jugnu destination
- Copy-migrate PropAi source files into jugnu/ as stubs marked # MIGRATED FROM PropAi: &lt;path&gt;

- ma_poc/fetch/\* → jugnu/ember/\*
- ma_poc/pms/detector.py → jugnu/glow/platform_detector.py
- ma_poc/pms/resolver.py → jugnu/glow/resolver.py
- ma_poc/pms/adapters/base.py → jugnu/glow/base_adapter.py
- ma_poc/pms/adapters/generic.py → jugnu/glow/generic_adapter.py
- ma_poc/models/scrape_profile.py → jugnu/profile.py
- ma_poc/services/profile_store.py → jugnu/profile_store.py
- ma_poc/services/profile_updater.py → jugnu/profile_updater.py
- ma_poc/validation/\* → jugnu/validation/\*
- ma_poc/discovery/dlq.py → jugnu/dlq.py
- services/llm_extractor.py → jugnu/spark/extraction_llm.py (stub)
- llm/interaction_logger.py → jugnu/observability/trace.py (stub)

Gate: repo exists, CI runs, pip install -e . works, docs/SOURCE_AUDIT.md exists

## **Phase 1 - Core Contracts + Skill Schema**

- Implement jugnu/skill.py - full Skill schema from Section 2.1. Every field must have a docstring comment. Note: no profile_storage_path in JugnuSettings - Jugnu does not own persistence.
- Implement jugnu/spark/skill_memory.py - SkillMemory, ImprovementSignal, ConsolidationLogEntry from Section 3.1
- Implement jugnu/contracts.py - Blink (with llm_profile: SkillMemory), CrawlInput, CrawlStatus, FetchResult, AdapterResult
- Migrate jugnu/profile.py from PropAi's scrape_profile.py. Remove cluster_id (dead field). Add: external_sources: list\[str\] in NavigationConfig.
- Write tests/test_skill.py and tests/test_skill_memory.py - 10 tests each covering: Skill serialization, SkillMemory.is_stale_for(), ImprovementSignal accumulation, compute_hash()

Gate: pytest tests/test_skill.py tests/test_skill_memory.py pass; mypy clean; from jugnu import Jugnu, Skill, Blink, SkillMemory works

## **Phase 2 - Ember Engine (Fetch Layer)**

- Refactor jugnu/ember/fetcher.py from PropAi source. Remove all ma_poc.\* imports. Accept FetchTask, return Jugnu FetchResult.
- Refactor stealth.py - keep 8-identity pool + SHA256 mapping
- Refactor proxy_pool.py - keep health scoring (±0.05/±0.25, quarantine <0.25)
- Keep rate_limiter.py and captcha_detect.py as-is (no PropAi imports)
- Implement change_detector.py - RenderMode: HOT + <1 day → GET; else RENDER
- Write tests/test_ember/ with mock Playwright pages

Gate: pytest tests/test_ember/ pass; no ma_poc.\* imports remain; fetcher.py never raises

## **Phase 3 - Lantern Engine (Discovery Layer)**

- Implement jugnu/lantern/link_extractor.py - extract hyperlinks and XHR captures from FetchResult
- Implement jugnu/lantern/link_ranker.py - rank_deterministic() uses SkillMemory.high_confidence_api_patterns and link_keywords. Returns scored list. Fires BEFORE any Prompt-1 call.
- Implement jugnu/lantern/api_heuristics.py - generalize PropAi's looks_like_availability_api() and response_looks_like_units(). Replace hardcoded rent/unit vocabulary with skill.output_schema.fields + SkillMemory.confirmed_field_synonyms.
- Implement jugnu/lantern/discovery_prompt.py - build_prompt1() generating Prompt-1 text. Injects SkillMemory.prompt1_context and known_noise_patterns.

Gate: pytest tests/test_lantern/ pass; no hardcoded domain terms in api_heuristics.py (grep check); Prompt-1 not called when deterministic rank > threshold (mock test)

## **Phase 4 - Glow Engine (Extraction Cascade)**

- Implement jugnu/glow/base_adapter.py - GlowAdapter Protocol: pms_name, extract(), static_fingerprints()
- Refactor jugnu/glow/generic_adapter.py from PropAi generic.py. Replace PMS tier labels with domain-agnostic labels. Adapter receives Skill and SkillMemory not property CSV row.
- Implement jugnu/glow/tiers/ - one file per tier. Pure async functions (page, fetch_result, skill, skill_memory, profile) → list\[dict\]. Never raises.
- Implement jugnu/glow/schema_normalizer.py - maps raw extracted field names to OutputSchema using: (1) SkillMemory.confirmed_field_synonyms, (2) profile.api_hints.llm_field_mappings, (3) exact match.
- Implement jugnu/glow/platform_detector.py - port PropAi detector.py. Detection signals come from SkillMemory.platform_fingerprints + SourceHint.api_patterns.

Gate: pytest tests/test_glow/ pass; no spark imports in glow/ (grep check); every tier returns list\[dict\] or \[\] never raises

## **Phase 5 - Spark Engine: Warmup + SkillMemory**

- Implement jugnu/spark/provider.py - SparkProvider wrapping litellm.acompletion(). Log every call: model, prompt_stage, input_tokens, output_tokens, cost_usd. Cost via litellm.completion_cost().
- Implement jugnu/spark/content_cleaner.py - html_to_fit_markdown(): strip head/script/style/nav/footer, convert to Markdown via html2text, BM25 relevance filter against skill.general_instructions. chunk_content(): overlapping windows using litellm.token_counter().
- Implement jugnu/spark/warmup.py - run_warmup(skill, spark) → SkillMemory. Pure Skill analysis, NO page load. Calls Prompt-5 from prompts/warmup.txt. Populates all SkillMemory fields. Sets skill_hash = SkillMemory.compute_hash(skill.name, skill.version).
- Write prompts/warmup.txt exactly as specified in Section 7.1
- Write tests/test_spark/test_warmup.py: warmup returns valid SkillMemory; all required fields populated; skill_hash correct; SkillMemory.is_stale_for() returns False for same skill

Gate: pytest tests/test_spark/test_warmup.py pass; warmup never fetches a URL (mock check); html_to_fit_markdown reduces 50KB fixture to <15KB

## **Phase 6 - Spark Engine: Extraction Prompts 1-4**

- Implement jugnu/spark/discovery_llm.py - rank_with_llm(). Calls Prompt-1. Parses improvement_signal from response. Appends to SkillMemory.pending_signals.
- Implement jugnu/spark/extraction_llm.py - extract_with_llm(). Calls html_to_fit_markdown() FIRST. Chunks if needed. Calls Prompt-2 per chunk, merges records. Parses improvement_signal. Appends to pending_signals.
- Implement jugnu/spark/merge_llm.py - merge_with_llm(). Calls Prompt-3. No improvement_signal.
- Implement jugnu/spark/external_ranker_llm.py - rank_external_with_llm(). Calls Prompt-4. Parses improvement_signal. Appends to pending_signals.
- Implement jugnu/spark/crystallizer.py - profile_crystallizer(). Takes field_mappings from Prompt-2 output, writes LlmFieldMapping to ScrapeProfile via ProfileStore-compatible update.
- Write all prompt templates: prompts/discovery.txt, extraction.txt, merge.txt, external_rank.txt as per Section 7

Gate: pytest tests/test_spark/test_prompts.py pass; every Prompt-1/2/4 call produces an improvement_signal in pending_signals (test with mock LLM); extract_with_llm never sends raw HTML (grep check)

## **Phase 7 - Spark Engine: Memory Consolidation (Prompt-6)**

- Implement jugnu/spark/consolidator.py - consolidate(skill_memory, spark, trigger) → None (mutates skill_memory in place). Calls Prompt-6. Parses full updated SkillMemory from response. Appends ConsolidationLogEntry. Clears pending_signals. Updates total_consolidation_cost_usd.
- Implement \_maybe_consolidate(skill_memory, spark, settings) - checks both batch trigger and smart trigger as specified in Section 4 Prompt-6 mechanics. Called by Swarm after each Blink.
- Implement run-end consolidation - called inside crawl() after all URLs complete, before return.
- Write prompts/consolidation.txt exactly as specified in Section 7.6
- Write tests/test_spark/test_consolidator.py: batch trigger fires at N signals; smart trigger fires on 3 new platform confirmations; pending_signals cleared after consolidation; memory_version increments; consolidation_log has entry with trigger type

Gate: all consolidator tests pass; a 150-URL mock run produces exactly 3 batch consolidations (50+50+50) plus 1 run-end; smart trigger test passes with 3-confirmation mock

## **Phase 8 - Profile Lifecycle + Drift**

- Refactor jugnu/profile_updater.py - update_after_blink(). Generalize: minimum_fields threshold uses skill.output_schema.minimum_fields, not hardcoded keys.
- Refactor jugnu/drift_detector.py - detect_drift(). Unit count drop threshold uses last_unit_count. All-null check uses skill.output_schema.minimum_fields.
- Implement jugnu/cluster_learner.py - find_cluster(profile, all_profiles): groups by pmc + platform_guess + json_path_signature. bootstrap_from_cluster(): copies api_hints+dom_hints, sets maturity=WARM.

Gate: COLD→WARM→HOT→COLD cycle test passes; cluster bootstrap test (new profile starts WARM from matching cluster, no warmup call)

## **Phase 9 - Validation + Merging**

- Refactor jugnu/validation/schema_gate.py - record_is_substantive() uses skill.output_schema.minimum_fields. batch_passes_gate() threshold from settings.min_success_threshold.
- Refactor jugnu/validation/identity_fallback.py - compute_primary_key() uses output_schema.merging_keys as hash inputs.
- Wire Prompt-3 merge flow into crawler.py: if CrawlInput.previous_records non-empty AND new records extracted → call merge_with_llm().
- Refactor jugnu/validation/cross_run_sanity.py - detect_value_swings() on any numeric fields in output_schema.

Gate: pytest tests/test_validation/ pass; no hardcoded 'rent','sqft','unit_id' in validation/ (grep check)

## **Phase 10 - crawl() API + Swarm Concurrency**

- Implement jugnu/crawler.py - class Jugnu. warm_up() and crawl() as specified in Section 5.
- warm_up(): if skill_memory passed in and not stale → return it (skip warmup). Else run run_warmup().
- crawl() orchestration loop per URL: load profile → change detection → fetch → discovery → extraction → external rank if needed → validation → merge if previous_records → profile update → \_maybe_consolidate → carry-forward if FAILED → report → return Blink with scrape_profile + llm_profile.
- Implement Swarm using asyncio.Semaphore. Pool size: min(RAM/250MB \* 0.7, cpu_count\*2, settings.max_concurrent_crawls) clamped \[1, 32\].
- Run-end consolidation: after Swarm drains, consolidate remaining pending_signals with trigger='run_end'.

Gate: end-to-end integration test with mock URLs returns Blinks with status != ERROR; 5-URL concurrent test with timing; blink.llm_profile.memory_version > 1 after 50+ URL mock run; warm_up() not called when valid skill_memory passed in (mock assertion)

## **Phase 11 - Reporting + Observability**

- Implement jugnu/reporting/blink_report.py - per-URL markdown including: status, tier_used, record count, llm_cost_usd, consolidations triggered
- Implement jugnu/reporting/run_report.py - success/fail/partial counts, tier distribution, total LLM cost (url-level + warmup + consolidation), SkillMemory version progression
- Implement jugnu/reporting/llm_cost_report.py - cost by prompt stage (P1-P6), by model, by URL
- Implement jugnu/observability/trace.py - emit(), TraceEvent. Key events: WARMUP_COMPLETE, CONSOLIDATION_FIRED (with trigger type), SMART_TRIGGER_DETECTED, DISCOVERY_RANKED, TIER_ATTEMPTED, TIER_WON, LLM_CALLED, PROFILE_UPDATED, DRIFT_DETECTED, CLUSTER_MATCHED
- Implement jugnu/observability/cost_ledger.py - SQLite per-URL, per-prompt-stage cost

Gate: emit() never raises; cost_ledger.db written after a mock run; run_report shows correct SkillMemory version progression

## **Phase 12 - Examples + Documentation + Tests**

- Write examples/real_estate/skill.py - complete Skill with 4 SourceHints (rentcafe, entrata, appfolio, sightmap). Include general_instructions with 3 real-world examples.
- Write examples/finance/skill.py - stock price + volume, Yahoo Finance / MarketWatch hints
- Write examples/sports/skill.py - match scores + standings, ESPN-style aggregator hints
- Write examples/news/skill.py - headline + summary, news publisher hints
- Each examples/\*/run.py must be runnable with 2-3 sample URLs
- Write complete module-level docstrings for all jugnu/ modules
- Write README.md: installation, 5-line quickstart, SkillMemory lifecycle diagram, example Skills
- Achieve 80%+ test coverage

Gate: pytest tests/ pass; coverage >= 80%; python examples/real_estate/run.py completes without error

## **Phase 13 - PR Creation + CI + Release**

- Create one GitHub PR per phase (P0-P12) against main
- CI workflow: pytest, mypy, ruff lint on every PR
- GitHub release tag v0.1.0 after all PRs merge
- Publish to PyPI as jugnu==0.1.0

Gate: all PRs open with CI passing; pip install jugnu works; from jugnu import Jugnu, Skill, SkillMemory succeeds

# **9\. Global Coding Conventions (Non-Negotiable)**

| **Convention**             | **Rule**                                                                                    | **Reason**                                      |
| -------------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Pydantic                   | Always model.model_dump(mode='json'). Never .dict()                                         | Pydantic v2 breaking change                     |
| Hashing                    | Always hashlib.sha256. Never built-in hash()                                                | hash() is non-deterministic across processes    |
| Concurrency                | asyncio.Semaphore for browser slots. asyncio.Lock for profile file writes                   | Prevents pool exhaustion and profile corruption |
| Playwright                 | Always context.close(). Never browser.close()                                               | Prevents resource leaks                         |
| Never-fail                 | Every layer returns structured failure. No raw raise in pipeline code                       | One URL must never crash the entire crawl       |
| No hardcoded domains       | No 'rentcafe','entrata','apartment','rent' in jugnu/ (only in examples/)                    | jugnu is domain-agnostic                        |
| LLM isolation              | Only jugnu/spark/ imports litellm. Never jugnu/glow/ or jugnu/ember/                        | Clean separation of concerns                    |
| fit_markdown required      | extract_with_llm() always calls html_to_fit_markdown() before sending content               | Reduces tokens 50-80%                           |
| ImprovementSignal required | Prompt-1/2/4 responses without improvement_signal are retried once                          | Signal collection is non-negotiable             |
| Profile writes             | Always through profile_store.ProfileStore.save(). Never write JSON directly                 | Version tracking + audit copies                 |
| SkillMemory ownership      | Jugnu mutates skill_memory in-place during crawl. Caller persists it. No internal file I/O. | Clean caller contract                           |
| Test command               | pytest . --ignore=examples --ignore=.jugnu                                                  | Consistent runner                               |

## **9.1 pyproject.toml**

\[project\]

name = "jugnu"

version = "0.1.0"

description = "Self-learning web crawler for domain-specific data extraction"

license = { text = "Apache-2.0" }

requires-python = ">=3.11"

dependencies = \[

"playwright>=1.40.0",

"pydantic>=2.0.0",

"litellm>=1.30.0",

"html2text>=2024.2.26",

"rank-bm25>=0.2.2",

"markdownify>=0.12.1",

"aiofiles>=23.0.0",

"httpx>=0.27.0",

"beautifulsoup4>=4.12.0",

"lxml>=5.0.0",

\]

\[project.optional-dependencies\]

dev = \["pytest>=8.0","pytest-asyncio>=0.23","mypy>=1.9","ruff>=0.3","pytest-cov>=5.0"\]

# **10\. Example Skill Definitions**

## **10.1 Real Estate - Apartment Availability**

REAL_ESTATE_SKILL = Skill(

name='apartment_availability', version='1.0',

description='Extract unit-level rent and availability from apartment websites',

output_schema=OutputSchema(

fields=\['unit_id','floor_plan_name','bedrooms','bathrooms','sqft',

'rent_low','rent_high','available_date','availability_status','confidence'\],

primary_key='unit_id',

merging_keys=\['unit_id','floor_plan_name'\],

minimum_fields=\['rent_low','bedrooms'\],

),

general_instructions='''

Extract all available apartment units from this property website.

Minimum: monthly rent and bedroom count.

Examples:

\- '2BR/2BA, 950sqft, \$2,450/mo, Available May 1' → rent_low=2450, bedrooms=2

\- 'Studio, \$1,800-\$1,950/mo, Now' → rent_low=1800, rent_high=1950, bedrooms=0

\- '3BR Penthouse, \$5,200/mo, Waitlist' → availability_status=WAITLIST

Data on pages named Floor Plans, Availability, Apartments.

Many sites load via XHR - watch /api/getApartments, /availability, /floorplans.

''',

source_hints=\[

SourceHint(platform='rentcafe', api_patterns=\['/api/getApartments','/GetApartments'\], link_keywords=\['floor-plans','availability'\]),

SourceHint(platform='entrata', api_patterns=\['/api/v1/properties','/module/widgets/'\], link_keywords=\['floor-plans'\]),

SourceHint(platform='appfolio', api_patterns=\['/api/available_rentals'\], link_keywords=\['available-units'\]),

SourceHint(platform='sightmap', api_patterns=\['sightmap.com/api'\], link_keywords=\['site-map','map'\]),

\],

llm=LiteLLMSettings(model='openai/gpt-4o-mini', temperature=0.0),

settings=JugnuSettings(max_concurrent_crawls=8, memory_consolidation_batch_size=50),

)

## **10.2 Finance - Stock Data**

FINANCE_SKILL = Skill(

name='stock_market_data', version='1.0',

output_schema=OutputSchema(

fields=\['ticker','company_name','price','change_pct','volume','market_cap','pe_ratio','timestamp'\],

primary_key='ticker', merging_keys=\['ticker'\], minimum_fields=\['ticker','price'\],

),

general_instructions='''

Extract stock market data. Minimum: ticker symbol and current price.

Examples: 'AAPL 184.32 +1.2% vol 52.3M'; 'TSLA rose 3.2% to \$242.10'

Data in tables, JSON via /v8/finance/chart/, or inline text.

''',

source_hints=\[

SourceHint(platform='yahoo_finance', api_patterns=\['/v8/finance/chart/','/v10/finance/quoteSummary/'\]),

SourceHint(platform='marketwatch', api_patterns=\['/api/dylan/quotes/'\]),

\],

llm=LiteLLMSettings(model='openai/gpt-4o-mini'),

settings=JugnuSettings(max_external_depth=1, memory_consolidation_batch_size=25),

)

## **10.3 Sports - Match Scores**

SPORTS_SKILL = Skill(

name='sports_scores', version='1.0',

output_schema=OutputSchema(

fields=\['match_id','home_team','away_team','home_score','away_score','match_date','competition','status'\],

primary_key='match_id', merging_keys=\['home_team','away_team','match_date'\],

minimum_fields=\['home_score','away_score','home_team','away_team'\],

),

general_instructions='''

Extract match scores and results.

Examples: 'Arsenal 2-1 Chelsea, EPL'; 'Lakers 112 Warriors 98 - Final'

Status: LIVE | FT | HT | UPCOMING

APIs often at /api/scores, /fixtures, /results, /livescore.

''',

source_hints=\[

SourceHint(api_patterns=\['/api/scores','/api/fixtures','/api/results','/livescore'\],

link_keywords=\['scores','results','fixtures','standings'\]),

\],

llm=LiteLLMSettings(model='openai/gpt-4o-mini'),

)

# **11\. GitHub PR Handoff Process**

## **PR Title Convention**

feat(jugnu): Phase 0 - Repo bootstrap + source audit

feat(jugnu): Phase 1 - Core contracts + Skill schema + SkillMemory

feat(jugnu): Phase 2 - Ember engine (fetch layer)

feat(jugnu): Phase 3 - Lantern engine (discovery)

feat(jugnu): Phase 4 - Glow engine (extraction cascade)

feat(jugnu): Phase 5 - Spark: Warmup + SkillMemory init

feat(jugnu): Phase 6 - Spark: Extraction prompts 1-4

feat(jugnu): Phase 7 - Spark: Memory consolidation Prompt-6 + smart trigger

feat(jugnu): Phase 8 - Profile lifecycle + drift + cluster learning

feat(jugnu): Phase 9 - Validation + merging

feat(jugnu): Phase 10 - crawl() API + Swarm concurrency

feat(jugnu): Phase 11 - Reporting + observability

feat(jugnu): Phase 12 - Examples + docs + tests

feat(jugnu): Phase 13 - CI + v0.1.0 release

## **PR Description Template**

\## Summary

&lt;one paragraph - what this phase implements&gt;

\## Gate Results

\- \[ \] All named tests pass: pytest &lt;path&gt;

\- \[ \] mypy clean: mypy &lt;module&gt;

\- \[ \] No forbidden imports (grep checks from gate spec)

\- \[ \] &lt;phase-specific gate items&gt;

\## Source Mapping

| New File | Migrated From | Changes |

|---|---|---|

| jugnu/ember/fetcher.py | ma_poc/fetch/fetcher.py | Removed ma_poc.\* imports |

\## SkillMemory Impact

&lt;describe any changes to how SkillMemory is read, written, or improved&gt;

\## Known Limitations / Follow-on

&lt;incomplete items, gaps, P(N+1) dependencies&gt;

**Design principle summary:** Jugnu flashes precisely when needed (LLM only on COLD + consolidation). It grows brighter as it learns (SkillMemory v1 → v100 over a run). It remembers across lifetimes (llm_profile returned in every Blink). Pay once for warmup. Pay ~1/50th per URL for consolidation. Run the rest deterministically for free.