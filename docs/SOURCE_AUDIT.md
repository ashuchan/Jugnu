# Source Audit — PropAi → Jugnu Migration

PropAi code is **reference only** — logic is ported; naming and contracts follow the Jugnu spec.

## Migration Map

| New File | Source | Notes |
|---|---|---|
| `jugnu/ember/fetcher.py` | `ma_poc/fetch/fetcher.py` | Remove PropAi imports; accept FetchTask |
| `jugnu/ember/stealth.py` | `ma_poc/fetch/stealth.py` | 8-identity pool + SHA256 sticky keys |
| `jugnu/ember/proxy_pool.py` | `ma_poc/fetch/proxy_pool.py` | Health ±0.05/±0.25, quarantine <0.25 |
| `jugnu/ember/rate_limiter.py` | `ma_poc/fetch/rate_limiter.py` | PerHostTokenBucket, no PropAi deps |
| `jugnu/ember/captcha_detect.py` | `ma_poc/fetch/captcha_detect.py` | Pattern list only |
| `jugnu/ember/change_detector.py` | `ma_poc/discovery/change_detector.py` | HOT+<1day→GET else RENDER |
| `jugnu/lantern/link_extractor.py` | `ma_poc/discovery/frontier.py` | Generalized, no domain terms |
| `jugnu/lantern/link_ranker.py` | `ma_poc/discovery/scheduler.py` | Uses SkillMemory patterns |
| `jugnu/lantern/api_heuristics.py` | `ma_poc/discovery/` | Generalized with OutputSchema.fields |
| `jugnu/glow/platform_detector.py` | `ma_poc/pms/detector.py` | Fingerprints from SkillMemory |
| `jugnu/glow/resolver.py` | `ma_poc/pms/resolver.py` | Remove PropAi imports |
| `jugnu/glow/base_adapter.py` | `ma_poc/pms/adapters/base.py` | GlowAdapter Protocol |
| `jugnu/glow/generic_adapter.py` | `ma_poc/pms/adapters/generic.py` | Domain-agnostic; Skill+SkillMemory |
| `jugnu/glow/schema_normalizer.py` | `ma_poc/pms/adapters/_parsing.py` | OutputSchema via SkillMemory synonyms |
| `jugnu/profile.py` | `ma_poc/models/scrape_profile.py` | Remove cluster_id; add external_sources |
| `jugnu/profile_updater.py` | `ma_poc/services/profile_updater.py` | Uses minimum_fields not hardcoded keys |
| `jugnu/dlq.py` | `ma_poc/discovery/dlq.py` | Park + retry cadence |
| `jugnu/validation/schema_gate.py` | `ma_poc/validation/schema_gate.py` | Uses minimum_fields |
| `jugnu/validation/identity_fallback.py` | `ma_poc/validation/identity_fallback.py` | Uses merging_keys |
| `jugnu/validation/cross_run_sanity.py` | `ma_poc/validation/cross_run_sanity.py` | Any numeric fields |
| `jugnu/observability/cost_ledger.py` | `ma_poc/observability/cost_ledger.py` | Per-prompt-stage |

## Files NOT Migrated

| File | Reason |
|---|---|
| `ma_poc/scripts/daily_runner.py` | Replaced by `jugnu/crawler.py` |
| `ma_poc/scripts/jugnu_runner.py` | Replaced by `jugnu/crawler.py` |
| `ma_poc/pms/adapters/rentcafe.py` | Domain-specific; in `examples/real_estate/` |
| `ma_poc/pms/scraper.py` | Split across `glow/` tiers |
