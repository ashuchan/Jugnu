# Jugnu Bug Hunt Checklist (J9)

For each item: mark `[x]` when verified absent, or fix and re-test.

## Fetch layer (J1)
- [ ] `fetch()` never raises on any input
- [ ] Proxy-pool `pick()` returns None when empty
- [ ] Rate-limiter no deadlock under fuzz
- [ ] Conditional cache survives mid-run SQLite deletion
- [ ] Robots timeout capped at 5s
- [ ] CAPTCHA detector: no false-positives
- [ ] Browser contexts closed in all code paths
- [ ] Every `fetch.*` event carries `property_id`

## Discovery layer (J2)
- [ ] Scheduler never yields duplicate tasks
- [ ] Frontier deduplicates URLs
- [ ] DLQ: hourly→daily escalation at 6h
- [ ] Carry-forward fires on hard-fail, empty-records, validation-reject
- [ ] Sitemap: child-file cap = 10
- [ ] Change detector is pure (no side effects)

## Extraction layer (J3)
- [ ] `detect_pms()` never raises
- [ ] `detect_pms()` deterministic
- [ ] `get_adapter()` always returns something (unknown → generic)
- [ ] Resolver: max 5 hops
- [ ] On SSL error: no adapter called, no LLM invoked
- [ ] LLM/Vision only in `generic.py`
- [ ] No PMS literals outside adapter/detector/resolver
- [ ] `tier_used` = `<adapter>:<tier_key>`

## Validation layer (J4)
- [ ] Schema gate never raises
- [ ] Fallback ID uses `hashlib.sha256`
- [ ] Rent: rejects negative and >$50K
- [ ] Cross-run sanity flags, does not reject
- [ ] `next_tier_requested` only at >50% reject

## Observability (J5)
- [ ] `emit()` never raises
- [ ] Event ledger: crash-safe append
- [ ] Cost ledger: thread-safe writes
- [ ] Replay CLI: handles missing data gracefully

## Profile (J6)
- [ ] v1 JSON loads under v2 schema
- [ ] `schema_version = "v2"`
- [ ] LRU caps enforced on load

## Report (J7)
- [ ] Verdict is pure and deterministic
- [ ] Both JSON and markdown written
- [ ] SLO section present

## Integration (J8)
- [ ] 46-key output schema preserved
- [ ] State files backward-compatible
- [ ] Never-fail: no property crashes the run
- [ ] `model_dump(mode="json")` everywhere
- [ ] `hashlib.sha256` everywhere

## Cross-cutting
- [ ] No higher-layer imports in lower layers
- [ ] No `print()` in production code
- [ ] Async `finally` blocks close all contexts
- [ ] `json.loads()` always in try/except
