# Phase Report — Kling Native Audio GUI Integration Design

**Phase ID:** KLING-NATIVE-AUDIO-GUI-INTEGRATION-DESIGN  
**Status:** Complete (design only)  
**Date:** 2026-06-16  
**Implementation:** None — awaiting approval of design before P0 schema work

---

## 1. Phase Goal

Integrate **Kling 3.0 Pro Native Audio** as a first-class provider in the Product UI and Content Brain workflow, based on successful live benchmark (character voices, environment audio, breathing, emotional acting, Multishot 12s+3s).

---

## 2. Deliverables

| Deliverable | Path | Status |
|-------------|------|--------|
| Integration design (canonical) | `project_brain/KLING_NATIVE_AUDIO_GUI_INTEGRATION_DESIGN.md` | Created |
| Phase report | `project_brain/PHASE_KLING_NATIVE_AUDIO_GUI_INTEGRATION_REPORT.md` | Created |

---

## 3. Design Summary by Area

### 3.1 GUI changes

| Surface | Change |
|---------|--------|
| **Create Video** | Add **Video Audio Strategy** (Auto / Music Only / Narrator / Kling Native Audio) |
| **Create Video** | Expand **Video Provider** (Auto / Runway Gen-4 / Gen-5 / Kling 3.0 Pro Native Audio) |
| **Create Video** | Kling duration chips **15 / 30 / 45 / 60** with clip mapping helper text |
| **Create Video** | Preflight shows Kling story plan preview; Generate routes to Kling live engine (not Phase I) |
| **Results** | New **Video & Audio Provenance** block: provider, audio strategy, shot mode, clip count, native audio status |

**Default:** Auto for both audio strategy and provider.

### 3.2 Content Brain changes

**New pipeline (Kling mode only):**

```
Topic → Story → Kling Story Planner → Clip Planner → Shot Planner → Execution bundle
```

**Per-clip output:**

```json
{
  "clip_index": 1,
  "shot_1_prompt": "…",
  "shot_2_prompt": "…",
  "continuity_anchor": "…",
  "next_clip_reference_hint": "…"
}
```

Plus durations (12s / 3s), `first_frame_source`, and `native_audio_directives`.

Legacy `clip_prompts[]` + narrator post **bypassed** when `audio_strategy = kling_native_audio`.

### 3.3 Router changes

Two-stage Auto routing:

1. **Audio Strategy Router v2** — adds `kling_native_audio` (Class C-Kling) alongside music_only / narrator / cinematic  
2. **Video Provider Router** — resolves `kling_3_pro_native` when Kling audio selected

**Auto examples (from spec):**

| Content | Audio route |
|---------|-------------|
| Motivation, luxury, travel | Music Only |
| Mystery, educational, documentary | Narrator |
| Fantasy, animals, children, horror, mini movies, dialogue-heavy | **Kling Native Audio** |

### 3.4 Continuity architecture

- Clip N **Shot 2 (3s bridge)** → extract **last frame** → **first frame upload** for Clip N+1  
- Metadata: `kling_continuity_chain_v1` with per-clip extract/handoff status  
- Output isolated under `outputs/kling_multishot_live/`  
- Aligns with `KLING_STORY_ARCHITECTURE_DESIGN.md` continuity fields

### 3.5 Metadata schema

| Artifact | Purpose |
|----------|---------|
| `kling_story_plan_v1` | Full clip + shot plan |
| `kling_continuity_chain_v1` | Frame handoff chain |
| Run `audio_strategy` / `video_provider` blocks | Provenance for Results |
| `kling_provenance` (Results API) | UI display bundle |

### 3.6 Migration from narrator pipeline

| Aspect | Approach |
|--------|----------|
| Parallel paths | Runway + narrator **unchanged** for non-Kling |
| Re-storyboard | 4×10s → N×15s beats (not 1:1 stretch) |
| Post-processing | Skip ElevenLabs narration when Kling native authoritative |
| Fallback | Explicit downgrade to Runway + narrator on failure |
| Channel controls | `prefer_kling_native_audio` / `block_kling_native` flags |

### 3.7 Recommended implementation order

1. P0 — JSON schemas  
2. P1 — Duration planner + API validation  
3. P2 — Audio router v2 (`kling_native_audio`)  
4. P3 — Story / clip / shot planners  
5. P4 — Create Video UI  
6. P5 — Multi-clip live runner + continuity  
7. P6 — Results provenance  
8. P7 — Assembly + post-processing branch  
9. P8 — Channel profile + router tuning  
10. P9 — Legacy re-plan tooling (optional)

---

## 4. Benchmark Alignment

Live test (`KLING_MULTISHOT_LIVE_APPROVAL_GATED_REPORT.md`) validated:

| Capability | Design treatment |
|------------|------------------|
| Kling 3.0 Pro provider | First-class `kling_3_pro_native` provider ID |
| Native Audio ON | `kling_native_audio` strategy; skip narrator post |
| Multishot 12s + 3s | Default shot mode in planners + Results label |
| Dialogue / breathing / ambience | `native_audio_directives` + prompt suffix rules |
| Approval-gated Generate | Preserved in P5 execution wiring |

---

## 5. Explicit Non-Goals (This Phase)

- No UI code changes  
- No Content Brain planner implementation  
- No router code changes  
- No Generate automation without approval  
- No migration execution on existing runs  

---

## 6. Open Decisions (For Operator Review)

| # | Question | Recommendation |
|---|----------|----------------|
| 1 | Rename Class C `cinematic` vs new ID `kling_native_audio`? | **New ID** — keeps legacy ElevenLabs cinematic as fallback |
| 2 | Allow Kling at 15s only for v1 UI? | **No** — ship 15/30/45/60 together per architecture |
| 3 | Subtitles for Kling dialogue? | Optional pass from `dialogue_lines` metadata (P7) |
| 4 | Gen-5 provider | UI placeholder until map/automation exists |

---

## 7. Next Phase (After Design Approval)

**Suggested:** `PHASE-KLING-NATIVE-AUDIO-SCHEMA-P0` — implement JSON schemas + `validate_kling_story_plan.py` + duration planner Kling provider key.

---

## 8. References

- `project_brain/KLING_NATIVE_AUDIO_GUI_INTEGRATION_DESIGN.md` — full design  
- `project_brain/KLING_STORY_ARCHITECTURE_DESIGN.md`  
- `project_brain/PHASE_AUDIO_STRATEGY_ROUTER_DESIGN_REPORT.md`  
- `project_brain/KLING_MULTISHOT_LIVE_APPROVAL_GATED_REPORT.md`  
- `tools/kling_multishot_live_runner.py`  

---

**Phase complete — design only, no implementation.**
