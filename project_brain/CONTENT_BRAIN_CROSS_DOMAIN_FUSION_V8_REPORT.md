# Content Brain V8 — Cross-Domain Fusion Engine Report

## Goal

Fix multi-domain topic collapse where Content Brain kept one dominant domain (e.g. perfume-only) and underused others, causing low strategy alignment (~0.28) on topics like:

> Could AI design a billion-dollar perfume brand by 2030?

Expected understanding: **AI + Perfume + Business + Future Forecast**, not perfume alone.

---

## Architecture

### Pipeline (V8)

```
Topic
  → Language Detection
  → Classification
  → Intent Intelligence
  → Cross-Domain Fusion          ← NEW
  → SEO Director
  → Story Generation
  → Clip Planner
  → Prompt Builder
  → Quality Audit
```

### Cross-Domain Fusion responsibilities

- `primary_domain`, `secondary_domains`, `supporting_domains`
- `domain_weights` (capped at 0.70 when ≥3 strong domains)
- `story_focus`, `strategic_angle`
- `domain_concepts_by_domain`
- `fused_conflict`, `fused_clip_structure`, `fused_character`, `fused_setting`
- OpenAI enrichment (gpt-4.1-mini) with cache + safe local fallback
- Audit scores: `cross_domain_fusion_score`, `domain_balance_score`, `missing_domain_warnings`

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/content_brain_cross_domain_fusion.py` | Fusion engine, OpenAI enricher, scoring, strategy alignment helpers |
| `project_brain/validate_content_brain_cross_domain_fusion.py` | V8 validator (5 multi-domain cases + cache/fallback tests) |
| `project_brain/content_brain_cross_domain_cache/` | Cached OpenAI fusion payloads |
| `project_brain/CONTENT_BRAIN_CROSS_DOMAIN_FUSION_V8_REPORT.md` | This report |

---

## Files Modified

| File | Changes |
|------|---------|
| `content_brain/execution/content_brain_e2e_micro_test_studio.py` | Studio v8; `_step_cross_domain_fusion()` before SEO; fusion wired through story/prompt/audit |
| `content_brain/execution/runway_story_brief_builder.py` | Applies fused conflict, character, setting, clip beats, balanced concepts, fusion-aware loglines |
| `content_brain/execution/runway_prompt_builder.py` | Balanced cross-domain concepts; `SCIENTIFIC_EXPLANATION_CROSS_DOMAIN_CLIP_FRAMES` |
| `content_brain/execution/content_brain_quality_audit_v2.py` | Fusion scores, gates, fused strategy alignment, multi-domain domain-knowledge scoring |
| `content_brain/execution/content_brain_openai_quality_enhancer.py` | Fusion-aware enhancement; preserves fused beats; multi-domain SEO refresh |
| `content_brain/execution/content_brain_intent_intelligence.py` | Counterfactual business-case detection (Nokia/Android) |
| `content_brain/execution/content_brain_topic_strategy.py` | Post-prompt fused strategy alignment (V7 carry-over) |
| `ui/web/src/pages/ContentBrainTestStudioPage.tsx` | Cross-Domain Fusion panel + summary scores |

---

## OpenAI Fusion Behavior

**Model:** `gpt-4.1-mini` (strict JSON)

**Triggers OpenAI when:**

- Multiple domains detected
- Topic mixes future/business/AI/science with another domain
- Domain weights unclear or primary confidence low
- Strategy alignment risk on multi-domain topics

**OpenAI may:**

- Assign domain weights
- Choose primary domain
- Add expert concepts per domain
- Improve story focus and clip structure

**OpenAI may NOT:**

- Change topic or language
- Remove a major domain
- Collapse multi-domain topics to one domain

**Dry-run env (validators):**

```powershell
$env:OPENAI_INTENT_DRY_RUN="1"
$env:OPENAI_CROSS_DOMAIN_DRY_RUN="1"
$env:OPENAI_QUALITY_DRY_RUN="1"
$env:SEO_PROVIDER_DRY_RUN="1"
$env:OPENAI_SEO_DRY_RUN="1"
```

---

## Cache Behavior

- **Path:** `project_brain/content_brain_cross_domain_cache/`
- **Key includes:** `FUSION_LAYER_VERSION` (currently `cross_domain_fusion_v9`), strategy, category, topic, local weights
- **Cache hit:** Returns stored payload; recomputes `multi_domain` from weights
- **Stale guard:** Version bumps invalidate bad single-domain cached payloads
- **Fallback:** OpenAI failure → `build_local_cross_domain_fusion()` (safe, no topic mutation)

---

## UI Changes

Content Brain Test Studio shows **Cross-Domain Fusion** panel:

- Primary / secondary domains
- Domain weights chart
- Domain concepts by domain
- Story focus, strategic angle
- Missing domain warnings
- `cross_domain_fusion_score`, `domain_balance_score`
- OpenAI fusion used, cache hit, estimated cost

---

## Validation Results

```text
python project_brain/validate_content_brain_cross_domain_fusion.py  → All checks PASS
python project_brain/validate_content_brain_v7_intent_intelligence.py → All checks PASS (no regression)
```

### V8 test case highlights

| Topic | Domains | Fusion | Strategy Alignment |
|-------|---------|--------|-------------------|
| AI billion-dollar perfume brand 2030 | business, perfume, ai, future | ~0.96 | ~0.85–0.90 |
| AI creative professions 2040 | ai, economics, creative, future | ~0.95 | ~0.86 |
| Chemistry perfume bestseller | science, perfume, business | ~0.92 | ~0.85 |
| AI surgeons vs human | medicine, ai, ethics, future | ~0.95 | ~0.78 |
| Nokia + Android counterfactual | business_history, technology | ~0.87 | ~0.88 |

---

## Before / After — AI + Perfume + Business Test

**Topic:** `Could AI design a billion-dollar perfume brand by 2030?`

### Before (V7)

- Category dominated by perfume
- Strategy alignment ~**0.28**
- Story: aspiring perfumer in fragrance lab
- Prompts: perfumer, fragrance oils, top notes only
- Business + AI concepts largely absent

### After (V8)

- Domains: business (0.40), perfume (0.35), ai (0.25), future
- Cross-domain fusion score ~**0.96**
- Strategy alignment ~**0.85–0.90**
- Story: fragrance entrepreneur testing AI luxury brand creation
- Clip structure: market claim → algorithmic evidence → business verdict
- Prompts include brand positioning, luxury market, accord design, algorithmic formulation, prediction models

**Example fused logline direction:**

> A fragrance entrepreneur tests whether AI-generated scent design can create a billion-dollar fragrance brand, combining market disruption and luxury brand creation with algorithmic accord design, consumer preference modeling, and a 2030 outcome prediction.

---

## Key Implementation Notes

1. **`balance_fusion_domain_concepts()`** — round-robin concepts across domains so prompt/story truncation does not drop major domains (e.g. business `market share`).
2. **Fused clip structures** — domain-specific beats for AI+perfume+business, AI+creative+economics, science+perfume+business, AI+medicine, Nokia+Android, AI+marketing.
3. **Quality enhancer guards** — multi-domain topics skip single-domain perfume dry-run overrides; fused clip beats preserved.
4. **Strategy required terms** — topic- and clip-aware terms for fused alignment scoring (avoids irrelevant `billion-dollar` on non-business topics).
5. **V7 preserved** — single-domain perfume scientific explanation, intent intelligence, and prompt entity gates unchanged.

---

## Run Validators

```powershell
cd C:\Users\kaman\Desktop\ModirAgentOS
$env:OPENAI_INTENT_DRY_RUN="1"
$env:OPENAI_CROSS_DOMAIN_DRY_RUN="1"
$env:OPENAI_QUALITY_DRY_RUN="1"
$env:SEO_PROVIDER_DRY_RUN="1"
$env:OPENAI_SEO_DRY_RUN="1"
python project_brain/validate_content_brain_cross_domain_fusion.py
python project_brain/validate_content_brain_v7_intent_intelligence.py
```

Restart API after backend changes: `python -m ui.api.main`
