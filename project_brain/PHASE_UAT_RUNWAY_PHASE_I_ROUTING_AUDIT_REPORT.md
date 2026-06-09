# Phase UAT / Runway Phase I Routing Audit Report

**Date:** 2026-06-03  
**Scope:** UAT Runtime start path vs Phase I 3-Clip Continuity flow  
**Outcome:** Root cause confirmed — operator used **Generic UAT Runtime**, not Phase I. No provider-router or Runway browser automation changes required.

---

## Executive summary

The operator started from **Execution Center → UAT Runtime → Generate UAT Video**. That path runs the **generic supervised UAT pipeline** (Content Brain brief → `ProviderRuntimeEngine` → `RunwayBrowserProvider`). It does **not** invoke `RunwayLiveSmokeRunner` or `RunwayContinuitySemiAutoEngine`.

Observed behavior (image generation → direct video generation) matches the generic UAT/provider dispatch model, **not** the Phase I chain:

> Story → starter image → download/confirm → Use to Video (clip 1) → download clip 1 → Use Frame → clip 2 → … → remove image → report

**Fix applied:** clarity only — UAT is correctly generic; UI and reports now explicitly label it and warn operators. Phase I remains on **Runway Live Smoke → 3-Clip Continuity (Phase I)**.

---

## Root cause

| Factor | Finding |
|--------|---------|
| **Wrong entry point** | UAT Runtime tab was used instead of Runway Live Smoke Phase I tab |
| **Different engine** | UAT: `UATRuntimeEngine` → `ContentBriefOrchestrator` → `SessionPromptAdapter` → `ProviderRuntimeEngine` |
| **Phase I engine** | `RunwayLiveSmokeRunner` → `build_continuity_prompts` → `RunwayContinuitySemiAutoEngine` |
| **Approval plan** | UAT: supervised voice/video/assembly confirmations — **not** 7-gate Phase I plan |
| **Continuity flags** | UAT had no `clip_count=3`, `continuity_enabled`, `use_frame_chain`, or `phase_i_7_gate` |

There is **no routing bug** in the provider router. UAT was never wired to Phase I by design.

---

## Was UAT generic or Phase I?

**Generic UAT Runtime** — confirmed.

- `is_phase_i_continuity`: `false`
- `route_name`: `uat_generic_supervised_pipeline`
- `runtime_name`: `Generic UAT Runtime`
- `approval_plan`: `uat_supervised_voice_video_assembly`
- Does **not** create 7 Phase I gates
- Does **not** set `use_frame_after_clips=[1,2]`

---

## UAT Runtime start path (inspected)

1. **UI:** `ui/web/src/pages/UatRuntimePage.tsx` → `postUatRun()` → `POST /uat/run`
2. **API:** `ui/api/uat_runtime_service.py` → `UATRuntimeEngine.start()`
3. **Engine:** `content_brain/execution/uat_runtime_engine.py` → `run_uat_pipeline()`
   - `ContentBriefOrchestrator.run()` (brief + `video_format_plan.clip_count` from Content Brain)
   - `_run_video_stage()` → `ProviderRuntimeEngine.dispatch_by_id()` when `runway_browser` + real video confirmed
4. **Not called:** `RunwayLiveSmokeRunner`, `build_continuity_prompts`, `RunwayContinuitySemiAutoEngine`

---

## Phase I start path (correct for 3-clip continuity)

1. **UI:** `ui/web/src/pages/RunwayLiveSmokePage.tsx` → tab **3-Clip Continuity (Phase I)** → `RunwayLiveSmokeApprovalPanel` → `POST /runway-live-smoke/start` with `clip_count=3`
2. **Engine:** `content_brain/execution/runway_live_smoke_test.py` → `RunwayLiveSmokeRunner(clip_count=3)`
3. **Flow:** StoryBrief → Prompt Builder → 7 approval gates → Use Frame after clips 1–2 → remove image on clip 3

---

## Files inspected

| File | Role |
|------|------|
| `ui/web/src/pages/UatRuntimePage.tsx` | UAT Start button |
| `ui/web/src/pages/RunwayLiveSmokePage.tsx` | Phase H / Phase I tabs |
| `ui/web/src/components/RunwayLiveSmokeApprovalPanel.tsx` | Phase I live smoke UI |
| `ui/api/uat_runtime_service.py` | UAT API wrapper |
| `ui/api/main.py` | `/uat/run` route |
| `content_brain/execution/uat_runtime_engine.py` | UAT pipeline |
| `content_brain/execution/uat_runtime_profile.py` | UAT caps + routing metadata |
| `content_brain/execution/uat_real_video_bridge.py` | Runway queue bridge (generic) |
| `content_brain/execution/provider_runtime_engine.py` | Video dispatch |
| `content_brain/execution/session_prompt_adapter.py` | UAT prompts (not continuity builder) |
| `content_brain/execution/runway_live_smoke_test.py` | Phase I runner |
| `content_brain/execution/runway_continuity_semi_auto.py` | Phase I semi-auto |
| `content_brain/execution/runway_continuity_dry_run.py` | 7-gate plan |
| `content_brain/execution/runway_story_brief_builder.py` | StoryBrief (Phase I path) |
| `content_brain/execution/runway_prompt_builder.py` | Continuity prompts (Phase I path) |
| `providers/runway_browser_provider.py` | Provider dispatch (unchanged) |

---

## Files changed

| File | Change |
|------|--------|
| `content_brain/execution/uat_runtime_profile.py` | Added `uat_routing_snapshot()`, `UAT_RUNTIME_NAME`, `UAT_ROUTE_NAME`, routing fields on session block |
| `content_brain/execution/uat_runtime_engine.py` | Routing section in UAT report; routing fields in status payload |
| `content_brain/execution/runway_live_smoke_test.py` | `runtime_name`, `route_name`, `is_phase_i_continuity`, `approval_plan` on Phase I/H reports |
| `ui/web/src/utils/uatRuntimeLabels.ts` | `UAT_RUNTIME_MODE_LABEL`, `UAT_PHASE_I_ROUTING_WARNING` |
| `ui/web/src/pages/UatRuntimePage.tsx` | Visible generic label + Phase I warning banner |
| `ui/web/src/styles/uat-runtime.css` | Styles for label and warning |
| `project_brain/validate_uat_runway_phase_i_routing.py` | **New** routing audit validator |
| `project_brain/PHASE_UAT_RUNWAY_PHASE_I_ROUTING_AUDIT_REPORT.md` | **This report** |

**Not changed (per audit rules):** `providers/runway_browser_provider.py`, provider router, Runway browser automation, approval gate semantics, StoryBrief Builder, Prompt Builder core logic.

---

## Validation results

```bash
python project_brain/validate_uat_runway_phase_i_routing.py          # 43/43 PASS
python project_brain/validate_runway_story_brief_builder.py          # 34/34 PASS
python project_brain/validate_runway_phase_i_3clip_live_continuity.py # 26/26 PASS
```

Key routing checks:

- UAT labeled **Generic UAT Runtime**; `is_phase_i_continuity=false`
- UAT does not import or call `RunwayLiveSmokeRunner`
- Phase I simulate run: `clip_count=3`, 7 gates, `use_frame_after_clips=[1,2]`, `story_brief_present=true`
- No provider router / prompt builder / StoryBrief regressions

---

## Operator instruction — Phase I 3-Clip Continuity

### Use this (Phase I)

**Execution Center → Runway Live Smoke → 3-Clip Continuity (Phase I) → Start 3-Clip Live (CDP)**

Expect:

- 7 approval gates (1 starter image + 3 video generates + 3 downloads)
- Use to Video for clip 1
- Use Frame after clips 1 and 2
- Remove image after clip 3
- Report: `project_brain/runway_phase_i_3clip_last_report.json` with `is_phase_i_continuity=true`

### Do not use this for Phase I

**Execution Center → UAT Runtime → Generate UAT Video**

That path is **Generic UAT Runtime** — full content factory test (Content Brain → video → voice → subtitle → assembly). It does **not** run Phase I continuity chaining.

The UAT page now shows:

- Label: **Generic UAT Runtime**
- Warning: directs operators to Runway Live Smoke → 3-Clip Continuity (Phase I)

---

## Report field reference

| Field | Generic UAT | Phase I Live Smoke |
|-------|-------------|-------------------|
| `runtime_name` | Generic UAT Runtime | Phase I 3-Clip Continuity Runtime |
| `route_name` | `uat_generic_supervised_pipeline` | `runway_live_smoke_phase_i_3clip` |
| `is_phase_i_continuity` | `false` | `true` |
| `approval_plan` | `uat_supervised_voice_video_assembly` | `phase_i_7_gate` |
| `clip_count` | From Content Brain brief (variable) | `3` (fixed) |
| `use_frame_after_clips` | `[]` | `[1, 2]` |
| `story_brief_present` | `false` | `true` (via Prompt Builder) |
| `expected_approval_gate_count` | N/A (not Phase I) | `7` |
