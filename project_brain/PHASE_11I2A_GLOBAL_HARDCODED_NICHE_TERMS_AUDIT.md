# Phase 11I-2A — Global Hardcoded Niche Terms Audit

**Status:** AUDIT COMPLETE (no code changes)  
**Date:** 2026-05-28  
**Scope:** Read-only global scan for niche-specific hardcoded terms, lists, templates, and defaults  
**Next phase:** **11I-2B — Minimal Fixes for CRITICAL Hardcoded Generic Terms**

---

## Executive Summary

| Classification | Count | System impact |
|----------------|-------|---------------|
| **CRITICAL** | 2 | Hardcoded word lists/templates apply to **all topics** when their module runs — must not be copied into 11I-3+ |
| **WARNING** | 14 | Niche dictionaries / examples on **Content Brain** path with profile-keyed or generic fallbacks |
| **SAFE** | 18+ | Isolated legacy selfcare pipeline, niche profile JSON, tests, demos, or `__main__` blocks |

**Content Brain Runtime execution path (11G–11I-2) is clean:**  
`content_brain/execution/*` (including subtitle preflight/validator), `SessionNarrationAdapter`, Voice Runtime, and Video Runtime dispatch contain **no skincare/selfcare highlight lists or fixed niche word arrays**.

**Highest-risk finding:** `engines/subtitle_engine.py` hardcodes skincare-adjacent `highlight_words` and is still invoked by `pipelines/full_video_pipeline.py` and **Run Studio** in `ui/app.py`. It is **not** wired to 11I-2 Subtitle Runtime foundation — but must not be reused for 11I-3 cue generation.

---

## Methodology

### Search terms (non-exhaustive)

`skincare`, `selfcare`, `skin`, `glow`, `mask`, `beauty`, `radiant`, `hydrated`, `dark`, `horror`, `mystery`, `cat`, `football`, `finance`, `motivation`, `viral`, `cinematic`, `luxury`, `highlight_words`, niche dict patterns (`NICHE_*`, `DOMAIN_*`).

### Areas reviewed

| Area | Files / patterns |
|------|------------------|
| Subtitle stack | `engines/subtitle_engine.py`, `engines/subtitle_burner.py`, `content_brain/execution/subtitle_*` |
| Content Brain engines | `content_brain/engines/*.py`, orchestrators, providers |
| Content Brain execution | `content_brain/execution/*.py` |
| Legacy pipeline | `pipelines/full_video_pipeline.py`, `core/timeline_engine.py`, `core/selfcare_content_engine.py` |
| Legacy engines | `engines/*.py` (trend, SEO, visual, director, hook, etc.) |
| Profiles & config | `config/content_brain/profiles/*.json` |
| UI | `ui/app.py`, `ui/components/content_brain_panel.py` |
| Tests / demos | `test_*.py`, `project_brain/run_*.py`, engine `__main__` blocks |

### Path classification

| Path type | Description |
|-----------|-------------|
| **Generic runtime** | Content Brain brief → execution session → category runtime (video/voice/subtitle/assembly) |
| **Legacy selfcare** | `full_video_pipeline`, `full_selfcare_factory`, `TimelineEngine.build_selfcare_timeline()` |
| **Niche-specific config** | Profile JSON (e.g. `dark_mystery_profile.json`) — intentional per-channel packs |

---

## CRITICAL Findings

Hardcoded terms inside engine logic that **bias every topic** when that engine runs (no profile/topic injection).

### C-01 — `engines/subtitle_engine.py` — fixed highlight word list

| Field | Value |
|-------|-------|
| **Path** | `engines/subtitle_engine.py` |
| **Area** | `SubtitleEngine.__init__` (L10–29), `style_word()` (L57–71) |
| **Terms** | `glow`, `skin`, `mask`, `radiant`, `hydrated`, `beautiful`, `healthy`, `viral`, … |
| **Runtime path** | Legacy: `pipelines/full_video_pipeline.py`, `test_full_ai_video_pipeline.py`, `postprocess_existing_video.py`, `rebuild_existing_project.py` |
| **Not on** | Content Brain Runtime, 11I-2 subtitle preflight/validator |
| **Why it matters** | ASS caption styling highlights skincare-adjacent tokens for **any** narration text. A football or finance video would still get yellow zoom on words like “mask” or “glow” if they appear. |
| **11I-2B fix** | Do **not** port this list to 11I-3. Use `per-session highlight_words` from channel profile / semantic universe / narration keywords; topic-neutral fallback (e.g. empty list or emphasis on `{topic_tokens}` only). |

### C-02 — `engines/seo_package_engine.py` — fixed skincare hashtag/CTA pools

| Field | Value |
|-------|-------|
| **Path** | `engines/seo_package_engine.py` |
| **Area** | `SEOPackageEngine.__init__` (L17–49), `generate_title()` templates (L52–58), `generate_description()` (L69–71), keyword lists (L83–88) |
| **Terms** | `#selfcare`, `#skincare`, `#glowup`, `#beauty`, `#glassskin`, “Your Skin Needs This {topic}”, “selfcare routine”, … |
| **Runtime path** | Legacy: `pipelines/full_video_pipeline.py` step SEO |
| **Why it matters** | SEO output for **any** `{topic}` injects beauty/selfcare hashtags and skin-centric title templates regardless of channel. |
| **11I-2B fix** | Replace static pools with profile-driven `seo_rules.hashtags` / channel keywords; generic fallback: platform tags only (`#shorts`, `#reels`) + topic tokens. |

---

## WARNING Findings

Niche-specific content on **generic Content Brain** paths. Usually **profile-keyed** or has a **generic fallback** — but can influence output when niche matches or when simulated trends run without user topic.

### W-01 — `content_brain/engines/hook_engineering_engine.py` — `NICHE_DETAIL_HINTS`

| Field | Value |
|-------|-------|
| **Area** | `NICHE_DETAIL_HINTS` (L197–243), `_build_context()` (L324–339) |
| **Terms** | Per-niche: football replay, perfume skin chemistry, **selfcare** “ten minutes on skin”, horror hallway, … |
| **Path** | Generic Content Brain (hook generation) |
| **Fallback** | Unknown niche → `one concrete {niche_label} detail` (topic-neutral) |
| **Why it matters** | Active when profile `niche` matches a dict key (e.g. `selfcare`, `football`). |
| **11I-2B fix** | Prefer profile `hook_rules.detail_hints` over code dict; keep code dict as optional seed examples only. |

### W-02 — `content_brain/engines/story_architecture_engine.py` — `NICHE_VISUAL_HINTS`

| Field | Value |
|-------|-------|
| **Area** | `NICHE_VISUAL_HINTS` (L152–204), used at L298 |
| **Terms** | Football VAR, perfume on skin, horror hallway, … |
| **Fallback** | `GENERIC_VISUAL_HINTS` for unknown niches |
| **Fix** | Move visual beat hints to profile `visual_dna.beat_hints` when present. |

### W-03 — `content_brain/engines/story_intelligence_engine.py` — niche lighting branch

| Field | Value |
|-------|-------|
| **Area** | `_lighting_for_beat()` (L386–398), `NICHE_VISUAL_LEXICON` (L76–105) |
| **Terms** | `football` → “Broadcast monitor glow”; `dark_mystery` → low-key horror lighting |
| **Fallback** | `else` → natural motivated light; lexicon → `"general"` bucket |
| **Fix** | Read lighting from profile `visual_dna.lighting` first; keep niche branches as optional overrides. |

### W-04 — `content_brain/engines/trend_discovery_engine.py` — `SimulatedTrendAdapter.NICHE_ANGLES`

| Field | Value |
|-------|-------|
| **Area** | `NICHE_ANGLES` (L315–370), includes **selfcare** skin recovery angles |
| **Fallback** | `GENERIC_ANGLES` when niche unknown |
| **When active** | Auto-topic mode (empty user topic) + simulated/local trend source |
| **Fix** | Prefer semantic-universe / channel keyword angles over static dict; use `GENERIC_ANGLES` until profile supplies seeds. |

### W-05 — `content_brain/engines/semantic_universe_engine.py` — hardcoded domain packs

| Field | Value |
|-------|-------|
| **Area** | `DOMAIN_KEYWORDS`, `DomainPack` definitions (football, perfume, horror, …), `_detect_domain()` |
| **Terms** | football VAR, skin chemistry, horror, dark mystery, … |
| **Fallback** | `_build_generic_pack()` tokenizes `main_niche` → topic-neutral clusters |
| **Fix** | Already mostly safe for unknown niches; reduce hardcoded packs in 11I-2B by generating packs from channel identity only. |

### W-06 — `content_brain/engines/niche_relevance_filter_engine.py` — domain negative tokens

| Field | Value |
|-------|-------|
| **Area** | `DOMAIN_NEGATIVE_TOKENS`, `STRONG_DROP_MARKERS` (L33–99) |
| **Terms** | football vs mobile-legends, dark_mystery vs travel film, … |
| **Why** | Intentional cross-niche noise rejection — not output generation |
| **Fix** | Optional: load drop markers from profile; low priority. |

### W-07 — `config/content_brain/profiles/default_profile.json` — horror registry shortcuts

| Field | Value |
|-------|-------|
| **Area** | `niche_registry` (L23–28) maps `horror`, `dark_mystery`, … → `dark_mystery_profile.json` |
| **Default niche** | `"general"` (L7) — topic-neutral |
| **Why** | User selecting “horror” gets horror profile by design |
| **Fix** | None required; document that registry keys are explicit niche opt-in. |

### W-08 — `config/content_brain/profiles/dark_mystery_profile.json`

| Field | Value |
|-------|-------|
| **Area** | Full horror/mystery tone, visuals, forbidden “clean beauty vanity setups” |
| **Classification** | WARNING only if mis-selected; file is **niche-specific config** (intentional) |
| **Fix** | None — keep as specialized profile pack. |

### W-09 — `ui/app.py` — Run Studio launches legacy pipeline

| Field | Value |
|-------|-------|
| **Area** | L928–933 runs `python -m pipelines.full_video_pipeline` |
| **Impact** | Operator can trigger full selfcare stack (timeline, subtitle highlight list, SEO skincare tags) |
| **Fix** | Label Studio run as “Legacy Selfcare Pipeline”; gate behind explicit mode or deprecate in favor of Content Brain Runtime. |

### W-10 — `content_brain/engines/story_intelligence_engine.py` — `GENERIC_VISUAL_PATTERNS`

| Field | Value |
|-------|-------|
| **Area** | L64–74 (anti-generic audit list) |
| **Terms** | “dark room”, “cinematic b-roll”, “person looking shocked” |
| **Purpose** | **Reject** generic patterns — not generation bias |
| **Fix** | None; optionally broaden to profile-specific forbidden patterns. |

### W-11 — Engine `__main__` / demo blocks (football, perfume, horror examples)

| Files | Examples |
|-------|----------|
| `content_brief_orchestrator.py` | L631+ football/perfume/dark_mystery demo cases |
| `semantic_universe_engine.py`, `profile_loader.py`, `trend_discovery_engine.py`, providers | Football VAR smoke prints |
| `project_brain/run_11x_end_to_end_topic_to_voice_dry_run.py` | `TOPIC = "cat in the streets of Los Angeles"` |

**Impact:** None on production runtime unless scripts are run manually.  
**Fix:** Move demos to `project_brain/` runners only; guard with `if __name__ == "__main__"`.

### W-12 — `core/full_project_scanner.py` — project description text

| Field | Value |
|-------|-------|
| **Area** | L283–285 |
| **Terms** | “Autonomous AI Selfcare Video Factory”, “skincare/selfcare content factory” |
| **Impact** | Documentation/brain metadata only |
| **Fix** | Update scanner copy to “multi-niche Content Brain platform”. |

### W-13 — `content_brain/orchestrators/content_brief_orchestrator.py` — “Viral Content Brain” branding

| Field | Value |
|-------|-------|
| **Area** | Module docstring, default profile `project_name` |
| **Terms** | “Viral” as product name — not niche-specific |
| **Fix** | None required (brand label, not topic bias). |

### W-14 — `engines/subtitle_engine.py` — ASS header + demo block

| Field | Value |
|-------|-------|
| **Area** | ASS title “Viral TikTok Captions” (L113); `__main__` test (L182–185) glow mask text |
| **Impact** | Legacy/demo only |
| **Fix** | Same as C-01 when subtitle generation is rebuilt for 11I-3. |

---

## SAFE Findings (Legacy / Isolated)

These files contain heavy skincare/selfcare terms but are **not** on the Content Brain generic execution path. Preserve for isolated legacy use per project rules.

| ID | File | Area | Terms (sample) | Why SAFE |
|----|------|------|----------------|----------|
| S-01 | `core/timeline_engine.py` | `build_selfcare_timeline()` L23–50 | “skin feels tired”, “yogurt honey oats”, “glowing skin” | Only called from legacy pipeline |
| S-02 | `core/selfcare_content_engine.py` | Episode templates throughout | Luxury skincare, glow ritual, hydrated skin | Selfcare factory content source |
| S-03 | `pipelines/full_video_pipeline.py` | Full chain L230+ | Imports timeline, subtitle, SEO selfcare stack | Explicit legacy pipeline; excluded from 11H voice path |
| S-04 | `full_selfcare_factory.py` | Factory entry | Selfcare orchestration | Standalone legacy factory |
| S-05 | `engines/trend_engine.py` | Topic/hook/title pools L10–46 | glass skin, glow up, luxury skincare | Legacy trend picker |
| S-06 | `engines/trend_research_engine.py` | Trend DB L13–111 | category: skincare, korean skincare | Legacy research mock data |
| S-07 | `engines/viral_hook_engine.py` | Hook pools L16–56 | expensive skincare, selfcare night | Legacy hooks |
| S-08 | `engines/visual_scenario_engine.py` | Sets + prompt rules L19–247 | spa skincare, beauty studio, viral TikTok skincare | Legacy video prompts |
| S-09 | `engines/cinematic_motion_engine.py` | Motion presets L11–105 | macro skincare, beauty commercial | Legacy prompts |
| S-10 | `engines/ai_director_engine.py` | Shot/light/mood lists + demo L18–167 | skincare mask, glowing skin | Legacy director |
| S-11 | `engines/scene_continuity_engine.py` | Continuity bible L28–153 | glowing skin, skincare robe | Legacy continuity |
| S-12 | `engines/video_prompt_engine.py` | Wraps `SelfcareContentEngine` | All prompts selfcare-derived | Legacy prompt builder |
| S-13 | `engines/subtitle_burner.py` | `__main__` L49 | `final_selfcare_video.mp4` | Legacy postprocess demo path |
| S-14 | `core/content_series_planner.py` | Series topics L22–82 | glow routine, selfcare night | Legacy planning |
| S-15 | `core/master_orchestrator_engine.py` | Episode id L183 | `episode_01_glow_mask` | Legacy orchestrator string |
| S-16 | `test_full_ai_video_pipeline.py`, `test_selfcare_*.py` | Test fixtures | Skincare topics throughout | Tests only |
| S-17 | `test_runway_orchestrator_direct.py` | Prompt L6–19 | beauty commercial, glowing skin | Direct test script |
| S-18 | `content_brain/execution/*` (all) | — | **No niche keyword lists found** | Confirmed clean for 11G–11I-2 |

---

## Content Brain Runtime — Subtitle Stack Status (11I-2)

| Module | Niche hardcoding | Verdict |
|--------|------------------|---------|
| `subtitle_preflight_runtime_slot.py` | None | ✅ Clean |
| `subtitle_artifact_validator.py` | None | ✅ Clean |
| `category_runtime_compat.py` | None (schema only) | ✅ Clean |
| `session_narration_adapter.py` | Explicitly avoids TimelineEngine / legacy pipeline | ✅ Clean |
| `engines/subtitle_engine.py` | **CRITICAL list** | ⚠️ Legacy only — **do not wire to 11I-3** |

---

## Dependency Map (Simplified)

```text
Content Brain Runtime (generic)
  content_brief_orchestrator
    → hook_engineering_engine      [W-01 niche dict + generic fallback]
    → story_architecture_engine    [W-02]
    → story_intelligence_engine    [W-03]
    → trend_discovery_engine       [W-04]
    → semantic_universe_engine     [W-05]
    → profile_loader + JSON profiles [W-07/W-08]
  execution session
    → voice_preflight / live_voice   [clean]
    → subtitle_preflight (11I-2)     [clean]

Legacy Selfcare Pipeline (isolated)
  ui/app.py Run Studio → full_video_pipeline
    → timeline_engine (skincare script)
    → subtitle_engine (C-01 highlight_words)
    → seo_package_engine (C-02)
    → visual_scenario / ai_director / selfcare_content_engine [S-08–S-12]
```

---

## Fix Strategy (for Phase 11I-2B)

### Principles

1. **Generic engines must not contain fixed niche word lists** that apply to every topic.
2. **Do not delete** isolated legacy selfcare pipeline files in 11I-2B unless explicitly scoped.
3. **Do not modify** Voice Runtime, Video Runtime, Runway/Hailuo, or 11I-2 subtitle foundation behavior.

### Recommended injection sources (instead of hardcoded lists)

| Use case | Replace hardcoded list with |
|----------|----------------------------|
| Subtitle emphasis / highlight words | `channel_profile.highlight_keywords`, semantic universe tokens, narration TF-IDF/top nouns, `{topic}` tokens |
| SEO hashtags / CTAs | `profile.seo_rules.hashtags`, `profile.audience`, topic-derived tags |
| Hook detail hints | `profile.hook_rules.detail_hints` with code dict as last-resort seed |
| Visual beat hints | `profile.visual_dna.beat_hints` |
| Trend simulation angles | Semantic universe `topic_seed_pool`, channel `main_niche` decomposition |
| Fallback when profile sparse | Topic-neutral only: `#shorts`, `#reels`, `{topic}` word split — **never** skincare defaults |

### 11I-2B priority order

| Priority | Item | Effort |
|----------|------|--------|
| P0 | Ensure 11I-3 design **does not import** `engines/subtitle_engine.py` highlight list | Design gate |
| P1 | Add profile schema hooks for `highlight_keywords` (optional, empty default) | Small |
| P2 | Document legacy pipeline boundary in Run Studio UI (W-09) | Small |
| P3 | Migrate Content Brain `NICHE_*` dicts to profile overlays over time | Medium |

---

## Files Scanned (representative)

### Subtitle-related
- `engines/subtitle_engine.py` ⚠️ C-01
- `engines/subtitle_burner.py` ✅ S-13
- `content_brain/execution/subtitle_preflight_runtime_slot.py` ✅
- `content_brain/execution/subtitle_artifact_validator.py` ✅
- `content_brain/execution/category_runtime_compat.py` ✅

### Content Brain engines (all under `content_brain/engines/`)
- `hook_engineering_engine.py` ⚠️ W-01
- `story_architecture_engine.py` ⚠️ W-02
- `story_intelligence_engine.py` ⚠️ W-03, W-10
- `trend_discovery_engine.py` ⚠️ W-04
- `semantic_universe_engine.py` ⚠️ W-05
- `niche_relevance_filter_engine.py` ⚠️ W-06
- `title_thumbnail_engine.py` ✅ (demo football in `__main__` only)
- `viral_scoring_engine.py`, `retention_map_engine.py`, `content_decision_engine.py` ✅ (niche tuples in `__main__` only)
- `uniqueness_engine.py` ✅ (football in `__main__` demo)

### Content Brain execution
- All `content_brain/execution/*.py` ✅ clean

### Legacy pipeline & core
- `pipelines/full_video_pipeline.py` ✅ S-03 (isolated)
- `core/timeline_engine.py` ✅ S-01
- `core/selfcare_content_engine.py` ✅ S-02
- `full_selfcare_factory.py` ✅ S-04

### Legacy engines (`engines/`)
- `trend_engine.py`, `trend_research_engine.py`, `viral_hook_engine.py` ✅ S-05–S-07
- `visual_scenario_engine.py`, `cinematic_motion_engine.py` ✅ S-08–S-09
- `ai_director_engine.py`, `scene_continuity_engine.py`, `video_prompt_engine.py` ✅ S-10–S-12
- `seo_package_engine.py` ⚠️ C-02

### Config / UI
- `config/content_brain/profiles/default_profile.json` ⚠️ W-07
- `config/content_brain/profiles/dark_mystery_profile.json` ⚠️ W-08 (intentional niche pack)
- `ui/components/content_brain_panel.py` ✅ (defaults: `niche=general`, empty topic)
- `ui/app.py` ⚠️ W-09

### Tests / project_brain runners
- `test_full_ai_video_pipeline.py`, `test_selfcare_*.py`, `run_11x_*.py` ✅ S-16 / W-11

---

## Conclusion

- **No CRITICAL hardcoded niche lists** were found on the **active Content Brain Runtime / 11I-2 subtitle foundation** path.
- **Two CRITICAL legacy engines** (`subtitle_engine`, `seo_package_engine`) apply skincare-biased terms to **all topics** when the legacy pipeline runs — highest risk if copied into 11I-3.
- **Content Brain engines** use niche dictionaries with **acceptable generic fallbacks** but should gradually move to **profile-driven keywords** (11I-2B).
- **Legacy selfcare stack** remains properly isolated; do not remove in audit phase.

**Recommended next step:** Phase **11I-2B** — address P0/P1 items (subtitle highlight strategy + profile hook) before **11I-3 Subtitle Cue Generation Engine Design**.
