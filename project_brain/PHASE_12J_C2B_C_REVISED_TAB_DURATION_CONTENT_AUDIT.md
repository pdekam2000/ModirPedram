# PHASE 12J-C2B-C REVISED — Controlled Tab Observability + Default Duration + Content Variation Audit

**Date:** 2026-06-02  
**Status:** Audit / design only — no implementation unless explicitly approved  
**Operator context (revised):** Real Runway generation **succeeded** (including cat videos). The operator was watching a **different Runway tab** than Playwright controlled — automation looked idle while work happened elsewhere. Controlled-tab observability remains necessary for **operator clarity**, not because Runway failed.

**Inputs:** `PHASE_12J_C2B_B_RUNWAY_PROMPT_INJECTION_TRACE.md`, `PHASE_12J_C2B_C_RUNWAY_CONTROLLED_TAB_GEN45_PREP_DESIGN.md`, `PHASE_12J_C2A_RUNWAY_BROWSER_OBSERVABILITY_REPORT.md`, sessions `exec_uat_20260602_080026` (dog), `exec_uat_20260602_110110` (cat)

---

## Executive Summary

| Area | Finding | Design direction |
|------|---------|------------------|
| **A — Tab observability** | 12J-C2A-OBS already persists URL/title/open tabs; UI lacks **prominent tab index** and **“automation is here”** affordance | Extend OBS + UAT UI; optional `bring_to_front` for supervised UAT; implement **12J-C2B-C tab selector** (separate approval) — **no Runway generate logic change** |
| **B — Duration** | UAT defaults **45s**; Runway UI/browser targets **10s**; profile already has `uat_single_segment_safe_duration(runway_browser)=10` but **min validation is 15s** | Align default **10s** for UAT + document Runway clip duration; adjust min bound to **10** for non-smoke UAT; keep Hailuo smoke at **6s** |
| **C — Content** | Dog vs cat share **same beat skeleton** (HOOK + ESCALATION), **same camera/motion templates**, topic only swaps in lexicon/anchor | Root cause is **`StoryIntelligenceEngine` / `VisualOriginalityEngine`**, not Runway; composer **off** on cat UAT; **general** niche on both |

**Recommended next implementation step (priority):**  
1) **Tab observability UX + bring-to-front (supervised UAT only)** — highest operator value, low risk.  
2) **10s UAT default + validation alignment**.  
3) **Content structure diversity** in Content Brain (12J-D / scene template work) — separate phase; do not patch via Runway automation.

---

## Part A — Controlled Tab Observability Plan

### A.1 What already exists (12J-C2A-OBS)

| Capability | Status |
|------------|--------|
| Persist `controlled_page` (URL, title, `page_index`) | Implemented |
| Persist `open_pages[]` with `controlled` flag | Implemented |
| Coarse `runway_browser_obs.step` | Implemented |
| UAT panel: Video Runtime, Runway step, controlled URL/title | Implemented |
| Expandable open tabs when count > 1 | Implemented |

**Evidence (cat success session):** `exec_uat_20260602_110110` recorded controlled tab index **0** and a second Runway tab at index **1** (same generate URL family) — matches operator “wrong tab” hypothesis.

### A.2 Gap vs operator need

| Gap | Impact |
|-----|--------|
| **Tab index not shown** in main UAT rows (only in expandable list with ▶) | Operator cannot quickly see “automation = tab 0” |
| **No `bring_to_front`** | Controlled tab may stay behind the tab the operator watches |
| **`pages[0]` still used at attach** | Wrong tab may be selected before OBS records it (12J-C2B-C selector not built) |
| **Prep substeps** not in UI yet | Hard to distinguish “working on wrong tab” vs “stuck in prep” |
| **No explicit banner** | “Automation is controlling tab N” missing |

### A.3 Observability-only design (no generation logic change)

**Scope boundary:** Changes limited to **selection observability**, **session fields**, **UAT UI**, and **optional supervised `bring_to_front`**. No changes to `fill_prompt`, `click_generate`, wait/download, or credit-spending paths.

#### A.3.1 Session / API fields (extend `runway_browser_obs`)

| Field | Purpose |
|-------|---------|
| `controlled_page.page_index` | **Required in UI primary row** (global CDP index) |
| `controlled_page.context_index` | Optional context ordinal |
| `controlled_page.selection_mode` | `reuse_tab` \| `navigate_canonical` (when selector ships) |
| `controlled_page.brought_to_front` | bool + timestamp |
| `operator_hint` | Short string, e.g. `Watch tab 0 — marked ▶ in list` |
| `prep_step` | From 12J-C2B-C prep design (when implemented) |
| `probes.prompt_box_found` / `probes.generate_button_found` | Visibility only |

#### A.3.2 UAT UI (revise 12J-C2A panel)

**Primary rows (always visible during video stage):**

1. Video Runtime state (ACTIVE / etc.)
2. **Controlled tab index:** `Tab #0` (bold)
3. Runway step (+ prep step when available)
4. Controlled tab URL (mono)
5. Page title
6. **Prompt box ready:** Yes/No (probe)
7. **Banner (new):** `Playwright controls tab #N — look for ▶ in Chrome`

**Open tabs list:**

- Show even when only **one** Runway tab exists if multiple browser tabs total (ChatGPT + Runway).
- Controlled row: `▶ [0] Generative Session | Runway AI` + URL.
- Non-controlled Runway tabs: warn styling `Same URL — not controlled`.

#### A.3.3 Supervised UAT: bring controlled tab to front

| Rule | Design |
|------|--------|
| When | `confirm_real_video=true` and `video_provider=runway_browser` |
| Action | `page.bring_to_front()` on **selected** page after selection |
| Env kill-switch | `MODIR_RUNWAY_SKIP_BRING_TO_FRONT=true` |
| Safety | No Generate click; no navigation; no credits |
| OBS | `brought_to_front: true` |

**Rationale:** Operator confirmed success on non-watched tab; bringing automation tab forward prevents false “nothing happened” reports without changing generation.

#### A.3.4 Tab selection (deferred implementation, design locked in 12J-C2B-C)

Observability **documents** intended selection; implementation is **12J-C2B-C** (ranked generate-tab scoring, never blind `pages[0]`). Until then:

- OBS should record **actual** `pages[0]` attach if selector not shipped, with `selection_mode: legacy_pages_zero` so audits stay honest.

#### A.3.5 Stdout tags (additive)

```text
[RUNWAY_TAB_CONTROL] index=0 url=... brought_to_front=true
[RUNWAY_OPERATOR_HINT] Watch tab 0 in controlled Chrome profile
```

### A.4 Part A validation (no code yet)

- [ ] Multi-tab Chrome: operator sees **Tab #N** in UAT matching tab receiving keystrokes after bring-to-front.
- [ ] Duplicate Runway generate URLs: UI shows which index is controlled.
- [ ] Real video UAT: generation completes while operator watches **same** tab as OBS index.

---

## Part B — Default Duration Plan (10s)

### B.1 Current state

| Layer | Current value | Notes |
|-------|---------------|-------|
| `UatRuntimeConfig.duration_seconds` | **45** default | `uat_runtime_profile.py` |
| `UatRunRequest` / API schema | **45** default, `ge=6` smoke min via `UAT_LIVE_VOICE_SMOKE_MIN_DURATION_SECONDS` | API uses 6 min from profile import |
| UI `DEFAULT_FORM.durationSeconds` | **45** | `UatRuntimePage.tsx` |
| UI `UAT_DEFAULT_MIN_DURATION_SECONDS` | **15** | `uatRuntimeEligibility.ts` |
| Backend `UAT_MIN_DURATION_SECONDS` | **15** | `uat_runtime_profile.py` |
| Runway browser `set_duration_10s()` | Attempts **10s** in UI after prompt fill | `runway_browser_provider.py` |
| `UAT_SINGLE_SEGMENT_SAFE_DURATION` runway | **10** | Already aligned with Runway |
| Hailuo safe duration | **6** | Unchanged |
| Content Brain `video_format_plan` (cat session) | `clip_duration_seconds: 10`, `max_clip_duration_seconds: 10` | Brief can already plan 10s clips while UAT requests 45s total |

**Mismatch:** Operator configures Runway for **10s** clips; UAT defaults **45s** total duration → confusing voice/assembly planning and retention map windows (e.g. 0–20s) while each Runway clip is still 10s.

### B.2 Design: safe 10s default (Runway-aligned, not global provider forcing)

| Change | Proposed value | Scope |
|--------|----------------|-------|
| UAT default duration | **10** | `UatRuntimeConfig`, API schema default, UI `DEFAULT_FORM` |
| UAT minimum duration (non-smoke) | **10** | `UAT_MIN_DURATION_SECONDS`, `UAT_DEFAULT_MIN_DURATION_SECONDS`, pydantic `ge` on `UatRunRequest` when not smoke-only |
| UAT maximum | **90** | Unchanged |
| Live voice smoke min | **6** | Unchanged (`UAT_LIVE_VOICE_SMOKE_MIN_DURATION_SECONDS`) |
| Smoke auto-reduce | runway → **10**, hailuo → **6** | Unchanged logic in `apply_live_voice_smoke_duration_guard` |
| Runway browser automation | Keep `set_duration_10s()` | Already matches; optional env `RUNWAY_BROWSER_DEFAULT_DURATION_SECONDS=10` for documentation only |
| Hailuo / mock / Content Brain global caps | **No forced 10s** | Hailuo keeps 6s smoke safe; format planner keeps provider-specific `clip_duration_seconds` from catalog |
| Content Brief `user_duration_seconds` | Pass **10** from UAT by default | `ContentBriefRunRequest.user_duration_seconds` |

### B.3 Validation consistency matrix

| Scenario | Expected after change |
|----------|------------------------|
| Default UAT form load | Duration field shows **10** |
| Runway + real video, no real voice | Valid range **10–90** |
| ElevenLabs + confirm real voice (smoke) | Min **6**, auto-reduce to 10 if user enters >10 |
| User enters 8s | **Invalid** (below 10) unless smoke path allows 6–90 |
| User enters 45s | Valid; retention/voice plan uses 45s — intentional override |

**Design note:** Lowering general UAT min from 15 → 10 **blocks** 8–9s unless smoke guard applies. That is intentional for Runway 10s alignment.

### B.4 Files to touch (implementation reference only)

| File | Change |
|------|--------|
| `content_brain/execution/uat_runtime_profile.py` | `UAT_MIN_DURATION_SECONDS = 10`, `UatRuntimeConfig.duration_seconds = 10` |
| `ui/api/schemas/uat_runtime.py` | `default=10`, `ge` aligned with profile |
| `ui/web/src/pages/UatRuntimePage.tsx` | `durationSeconds: 10` |
| `ui/web/src/utils/uatRuntimeEligibility.ts` | `UAT_DEFAULT_MIN_DURATION_SECONDS = 10` |
| Docs / helper text | “Default 10s matches Runway Gen-4.5 clip setting” |

**Out of scope:** Changing Hailuo provider internal defaults; changing `video_format_planner` global max for all providers.

### B.5 Part B validation

- [ ] Fresh UAT page shows 10s default; submit without editing duration.
- [ ] `exec_uat_*` brief shows `target_duration_seconds` / clip plan consistent with 10s when operator does not override.
- [ ] Live voice smoke still reduces high durations to provider-safe cap.
- [ ] Runway browser still runs `set_duration_10s()` without regression.

---

## Part C — Content Variation Audit (Dog vs Cat)

### C.1 Prompt comparison (final strings to Runway)

**Source:** `execution_runtime.prompt_bundle.prompts` (what `SessionPromptAdapter` produced at dispatch).

#### Clip 1 (HOOK)

| Element | Dog (`exec_uat_20260602_080026`) | Cat (`exec_uat_20260602_110110`) |
|---------|----------------------------------|----------------------------------|
| Opening lexicon | `Open on dog: dog worked — and that is exactly why it feels wrong in General Short-Form....` | `topic-specific object in sharp focus highlighting cat during hook — specific to cat, not generic stock footage..` |
| Subject | (embedded in opening / texture line) | `cat evidence element` |
| Action | `Reveal dog detail entering frame` (via schema) | `Reveal cat detail entering frame` |
| Camera | `Tight macro on evidence detail` | **Same** |
| Movement | `shallow depth of field` | **Same** |
| Lighting | `Natural motivated light... high contrast accent on focal detail` | **Same** |
| Mood / pacing | `curiosity` | **Same** |
| Continuity | `Follows opening; sets up ESCALATION_BEAT.` | **Same** |

#### Clip 2 (ESCALATION)

| Element | Dog | Cat |
|---------|-----|-----|
| Opening lexicon | `close-up for emotion or detail; ... high-contrast mobile palette...` | `evidence detail macro shot highlighting cat during escalation — specific to cat...` |
| Action | `Contrast two readings of dog` (schema) | `Contrast two readings of cat` |
| Camera | `Slow push-in on contradicting detail` | **Same** |
| Movement | `Static hold` | **Same** |
| Lighting | `Natural motivated light with clear subject separation` | **Same** |
| Mood | `tension` | **Same** |

**Structural similarity score (audit):** ~85–90% identical **camera / beat / continuity skeleton**; topic substitution in lexicon, subject, and action strings only.

### C.2 End-to-end trace (dog vs cat)

```text
UAT topic "dog" | "cat"
  → ContentBriefOrchestrator
       → StoryBlueprint + RetentionMapEngine (platform beats, implementation_note templates)
       → StoryIntelligenceEngine.enhance()
            → SceneProgressionEngine: HOOK_BEAT + ESCALATION_BEAT for 2 clips
            → VisualOriginalityEngine._build_visual / _camera_for_beat / _action_for_beat
            → CinematicBeatEngine.build_director_shots → schema_director_shots
       → [optional] RunwayPromptComposer if flag ON at dispatch
  → SessionPopulationBuilder → session JSON
  → ProviderRuntimeEngine.dispatch()
       → SessionPromptAdapter.build() → prompt_bundle.prompts[]
  → RunwayBrowserOrchestrator → fill_prompt(prompt)
```

### C.3 Answers to required questions

#### 1. Is RunwayPromptComposer enabled during UAT?

**Default: No.** `enable_runway_prompt_composer()` defaults **false** unless session/env explicitly enables.

| Session | Composer at dispatch? | Evidence |
|---------|---------------------|----------|
| Cat `110110` | **No** | `prompt_bundle.clip_metadata[].lineage: null`; no `runway_composer_version` in dispatch bundle |
| Dog `080026` | **Yes** (brief) | `run_context.runway_composer_version: 12j_c_v1`, `runway_composed_clips[]` present |

UAT does **not** auto-enable composer. Dog session likely had `MODIR_ENABLE_RUNWAY_PROMPT_COMPOSER` or manual flag during that run.

#### 2. Final prompt: composer output or legacy visual lexicon?

| Session | Primary source |
|---------|----------------|
| Cat | **`schema_director_shots`** text from **StoryIntelligence** (`VisualOriginalityEngine` templates + `SessionPromptAdapter._compose_prompt`) |
| Dog | Composer **merged** hook/retention into shots, but **camera/action structure still from StoryIntelligence**; adapter assembled final string |

Composer changes **wording** and fold-in of retention/hook payloads; it does **not** today replace beat-fixed camera/motion tables.

#### 3. Does Content Brain generate different story structures for dog vs cat?

**No meaningful structure difference** for these runs:

- Same **niche:** `general` (both sessions).
- Same **clip count:** 2.
- Same **beat selection:** `SceneProgressionEngine._select_beats_for_clips` priority → **HOOK_BEAT + ESCALATION_BEAT**.
- Same **story mode / architecture** pattern; narrative questions differ only by token: `What does dog reveal about dog?` vs `What does cat reveal about cat?`
- `story_signature` / fingerprints differ (topic hash) but **scene/camera templates are beat-driven, not topic-class-driven**.

#### 4. Does VisualOriginalityEngine or composer collapse topics into the same structure?

| Component | Role |
|-----------|------|
| **VisualOriginalityEngine** | **Primary collapser** — `_camera_for_beat`, `_motion_for_beat`, `_action_for_beat`, `_lighting_for_beat` are **fixed per `beat_id`**; only `anchor` / `context.topic` / lexicon slot rotate |
| **RunwayPromptComposer** | Merges hook/retention/thumbnail fields into composed prompt; **does not** assign per-topic camera grammar when enabled |
| **Composer off** | Collapse still happens in **StoryIntelligence** before adapter |

#### 5. Are we still using general niche fallback?

**Yes.** Both sessions: `niche: "general"`, `source_niche: "general"`, retention/story copy references **“General Short-Form Content”**. UAT form default `niche: "general"` (`UatRuntimeConfig`).

Niche-specific profiles (e.g. `dark_mystery`) are **not** used unless operator changes niche.

#### 6. Why are scene/action/camera patterns almost identical?

**Root cause (code-level):**

```375:431:content_brain/engines/story_intelligence_engine.py
    def _camera_for_beat(self, beat_id: str) -> str:
        cameras = {
            "HOOK_BEAT": "Tight macro on evidence detail, shallow depth of field",
            "ESCALATION_BEAT": "Slow push-in on contradicting detail",
            ...
        }
    def _action_for_beat(self, beat_id: str, anchor: str) -> str:
        actions = {
            "HOOK_BEAT": f"Reveal {anchor} detail entering frame",
            "ESCALATION_BEAT": f"Contrast two readings of {anchor}",
            ...
        }
```

```280:292:content_brain/engines/story_intelligence_engine.py
        priority = ["HOOK_BEAT", "ESCALATION_BEAT", "PAYOFF_BEAT", "LOOP_SEED"]
        # 2-clip UAT always picks HOOK + ESCALATION
```

Retention map adds **platform** implementation notes (`VISUAL: one concrete texture...`, `camera angle or scene shift`) that are **topic-agnostic**; composer (when on) folds them in but does not diversify camera grammar.

#### 7. How to make prompts topic-specific beyond dog/cat swap?

| Lever | Design recommendation (future phases) |
|-------|--------------------------------------|
| **Topic class taxonomy** | Map topic → scene grammar (animal, person, place, object, event) before beat templates |
| **Beat camera tables** | Parameterize by topic class + niche profile, not only `beat_id` |
| **Visual lexicon rotation** | Use full `niche_visual_language[]` with anti-repeat across clips, not `index % len` only |
| **Scene count / beat mix** | Allow PAYOFF or CONTEXT for 2-clip shorts when topic needs explanation |
| **Niche profile in UAT** | Default niche from channel profile, not always `general` |
| **12J-D VisualOriginalityEngine** | Move enrichment to post-composer with **diversity audit** (design lock exists) |
| **Composer** | Enable only with **topic scene primitives** + diversity gate; flag off remains safe default |
| **Retention map** | Topic-bound implementation notes (e.g. cat behavior vs dog motion) at generation time |

**Explicitly not recommended:** Fixing repetition in `RunwayBrowserProvider.fill_prompt` or Runway UI automation.

### C.4 Retention map role

- **RetentionMapEngine** produces beat windows and `implementation_note` strings (VISUAL/AUDIO/CAPTION) tied to **platform** and **hook text** (cat/dog hook line inserted in caption slots).
- **Visual instructions** remain generic (“one concrete texture”, “camera angle or scene shift”).
- For 2-clip plans, notes for clip 0 vs clip 1 repeat the same VISUAL families; only clip index / time window changes.
- **Composer** (dog session) attaches retention payloads into `runway_composed_clips`; **cat** still has retention data in brief but composer was off at dispatch — final cat prompts still reflect StoryIntelligence + adapter only.

### C.5 Source of repeated structure (single table)

| Layer | Varies by topic? | Fixed structure? |
|-------|------------------|------------------|
| UAT topic string | Yes | — |
| Niche | No (general) | General short-form templates |
| Beat selection (2 clips) | No | HOOK + ESCALATION |
| VisualOriginalityEngine camera/motion/lighting | Token only | Per-beat tables |
| CinematicBeatEngine continuity | Wording | `Follows HOOK_BEAT; sets up close` pattern |
| SessionPromptAdapter | Appends camera lines | Same assembly rules |
| RunwayPromptComposer | Hook/retention merge | **Off** on cat; **on** on dog — still same camera lines |
| Runway browser | N/A | Types whatever string received |

**Exact source of repeated structure:** `content_brain/engines/story_intelligence_engine.py` — `VisualOriginalityEngine` + `SceneProgressionEngine` + `CinematicBeatEngine`, with **general** niche and **2-clip HOOK/ESCALATION** selection.

---

## Cross-Part Constraints (Rules Compliance)

| Rule | Compliance |
|------|------------|
| No Runway automation changes | Parts A and B observability/duration only; Part C is Content Brain |
| No voice/subtitle/assembly | Duration section notes voice smoke guards only |
| No implementation in this phase | This document only |
| Audit/design first | Satisfied |

---

## Recommended Next Implementation Steps (Priority Order)

| Priority | Phase ID | Scope | Approval needed |
|----------|----------|-------|-----------------|
| **P0** | 12J-C2B-C-UI-OBS | UAT: show **tab index** + operator banner; persist `operator_hint`, `brought_to_front`; supervised `bring_to_front` | Yes |
| **P1** | 12J-C2B-C-TAB | `RunwayPageSelector` — ranked tab selection, no `pages[0]` | Yes |
| **P1** | 12J-C2B-C-PREP | `RunwayGen45PrepEngine` substeps + prep OBS (from prior 12J-C2B-C design) | Yes |
| **P2** | 12J-C2B-C-DURATION | UAT default + min **10s**; docs; no Hailuo global force | Yes |
| **P3** | 12J-D / Content | Topic-class scene grammar, niche defaults, composer diversity gates | Separate design lock |

**Do not implement** wait/download (12J-C Step 2) or Runway prompt typing changes until tab observability is shipped — operator trust is the immediate bottleneck.

---

## Related Documents

| Document | Role |
|----------|------|
| `PHASE_12J_C2B_B_RUNWAY_PROMPT_INJECTION_TRACE.md` | Injection path + tab mismatch |
| `PHASE_12J_C2B_C_RUNWAY_CONTROLLED_TAB_GEN45_PREP_DESIGN.md` | Tab selector + prep state machine (full) |
| `PHASE_12J_C2A_RUNWAY_BROWSER_OBSERVABILITY_REPORT.md` | Current OBS baseline |
| `PHASE_12J_C_RUNWAY_PROMPT_COMPOSER_DESIGN_LOCK.md` | Composer vs 12J-D boundaries |
| `PHASE_12J_C_STEP2_RUNWAY_WAIT_DOWNLOAD_HARDENING_DESIGN.md` | Post-submit hardening (later) |

---

## Summary

Operator confirmation reframes the problem: **Runway works**; **visibility** and **expectations** (duration, prompt sameness) need design alignment. Controlled-tab observability should emphasize **which tab index** Playwright drives and optionally **bring that tab forward** in supervised UAT, without touching generation logic. Default **10s** UAT duration aligns UI, validation, and Runway’s 10s clip setting while leaving Hailuo on its own smoke-safe **6s**. Dog vs cat repetition is **not** a Runway defect — it originates in **StoryIntelligence beat templates** under **general** niche with **HOOK+ESCALATION** two-clip selection; composer is **off** on typical cat UAT and does not fix camera grammar when on.
