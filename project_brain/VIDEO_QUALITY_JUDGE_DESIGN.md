# Video Quality Judge AI — Design

**Phase:** `VIDEO-QUALITY-JUDGE-AI`  
**Status:** Design only — no implementation  
**Date:** 2026-06-16  

---

## 1. Problem Statement

ModirAgentOS can **generate** videos end-to-end (Runway, Kling Native Audio, assembly, publish package), but it **cannot automatically learn** from what was actually delivered.

| Today | Gap |
|-------|-----|
| Pre-generation scoring (`QualityAuditV2`, `ViralScoringEngine`, `StoryIntelligenceEngine`) | Scores **plans**, not **finished MP4s** |
| Delivery gate (`delivery_quality_gate`) | Binary PASS/FAIL on artifact integrity (duration, audio stream, subtitles) |
| Story/audio auditor (`story_audio_auditor`) | Validates **story package** before production |
| Visual continuity pipeline | Per-clip subject match, not holistic narrative judge |
| Results page | Shows delivery truth + pipeline metadata, no **holistic quality score** or **actionable feedback loop** |

**Goal:** After generation, run an **AI Video Judge** on the canonical deliverable, produce structured scores + improvement actions, and feed that back into Content Brain for the next run.

---

## 2. Design Principle — Extend, Do Not Duplicate

| Existing system | Role | Relationship to Video Judge |
|-----------------|------|----------------------------|
| `content_brain/execution/content_brain_quality_audit_v2.py` | Pre-run brief/prompt quality | **Input context** for judge (expected vs actual) |
| `content_brain/quality/story_audio_auditor.py` | Pre-run story/audio plan audit | **Baseline expectations** |
| `content_brain/platform/delivery_quality_gate.py` | Artifact integrity gate | **Prerequisite** — judge runs only if deliverable exists |
| `content_brain/engines/viral_scoring_engine.py` | Pre-run viral dimensions | **viral_score** calibration reference |
| `content_brain/vision/visual_continuity_pipeline.py` | Clip-level continuity | Feeds **continuity_score** sub-signals |
| `content_brain/platform/results_run_loader.py` | Results aggregation | **Surface** judge output on Results page |

**New module (future):** `content_brain/quality/video_quality_judge.py`  
**Not** a parallel story engine, viral engine, or delivery gate rewrite.

---

## 3. Workflow Placement

```text
Topic
  ↓
Content Brain (planning / prompts / story package)
  ↓
Generate Video (provider runtime)
  ↓
Assembly + Publish Package
  ↓
Delivery Quality Gate (integrity PASS/WARNING/FAIL)
  ↓
┌─────────────────────────────────────┐
│  AI Video Judge  (NEW)              │
│  Input: canonical MP4 + run metadata│
│  Output: VideoQualityJudgeResult    │
└─────────────────────────────────────┘
  ↓
Score + Feedback persisted to run folder
  ↓
Learning Loop (see VIDEO_LEARNING_LOOP_DESIGN.md)
  ↓
Next Content Brain run applies weight adjustments
```

**Trigger points (future):**

1. **Automatic** — after `delivery_quality_gate` PASS or WARNING (not FAIL-with-no-file)
2. **Manual** — Results page “Re-run Video Judge” button
3. **Batch** — `project_brain/reprocess_video_judge.py` for historical runs

**Explicit non-goals for v1 judge:**

- Does not click Generate or spend credits
- Does not replace delivery gate (integrity vs quality)
- Does not block publish by default (advisory mode v1; optional hard gate v2)

---

## 4. Evaluation Categories → Score Mapping

User-facing categories map to the **output schema** as follows:

| Category | Sub-dimensions | Primary score field |
|----------|----------------|---------------------|
| **1. Story Quality** | beginning, middle, ending, pacing | `story_score` |
| **2. Character Quality** | consistency, emotions, continuity | split: emotions → `story_score`; consistency → `continuity_score` |
| **3. Audio Quality** | dialogue, environment, immersion | `audio_score` |
| **4. Visual Quality** | realism, motion, cinematic feel | `visual_score` |
| **5. Viral Potential** | hook, retention, shareability | `viral_score` |

### 4.1 Story Quality (`story_score` 0–100)

| Signal | Source |
|--------|--------|
| Beginning hook strength | First 3s frame analysis + optional audio onset + story_package hook alignment |
| Middle escalation | Scene beat density vs planned `scene_progression` |
| Ending payoff | Final 5s + CTA/outro presence vs `resolution` / `ending_cta` |
| Pacing | Shot duration variance, dead air, abrupt cuts (ffprobe + scene change heuristic) |

### 4.2 Character Quality (feeds `story_score` + `continuity_score`)

| Signal | Source |
|--------|--------|
| Consistency | `visual_continuity_report` clip scores + subject memory |
| Emotions | `character_emotion_plan` vs detected performance (LLM + metadata) |
| Continuity | Cross-clip subject/setting drift |

### 4.3 Audio Quality (`audio_score` 0–100)

| Signal | Source |
|--------|--------|
| Dialogue clarity | Mean volume, speech band energy, subtitle alignment (if burned) |
| Environment | Ambience layer presence vs `environment_plan` |
| Immersion | Music/SFX/native-audio balance; no clipping; no silent gaps > 2s |

**Kling Native Audio path:** judge native in-video dialogue/ambience; **no ElevenLabs expectation**.

### 4.4 Visual Quality (`visual_score` 0–100)

| Signal | Source |
|--------|--------|
| Realism | Artifact detection heuristics + optional vision model |
| Motion | Per-clip motion smoothness (optical flow proxy or model) |
| Cinematic feel | Composition variance, lighting consistency, shot type diversity (`ai_director_v2`) |

### 4.5 Viral Potential (`viral_score` 0–100)

| Signal | Source |
|--------|--------|
| Hook | First-frame + first-line retention proxy |
| Retention | Pacing curve vs `retention_map` / hook package |
| Shareability | Emotional peak timing, novelty vs channel history |

Reuse **weights philosophy** from `ViralScoringEngine` but score **delivered artifact**, not brief.

---

## 5. Judge Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│ VideoQualityJudgeInput                                       │
│  run_id, video_path, provider, audio_strategy              │
│  story_package, assembly_manifest, continuity reports        │
│  channel_profile, preflight_plan (optional)                  │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ Signal Collectors (deterministic)                            │
│  • ffprobe: duration, streams, loudness                      │
│  • delivery_quality_gate checks (reuse)                      │
│  • visual_continuity_report                                  │
│  • story_visual_quality / cinematic_audio audits             │
│  • kling_native_audio metadata (if applicable)               │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ Optional Multimodal Extractors (v1.1+)                       │
│  • keyframe strip (1 fps × min(duration, 60s))               │
│  • audio waveform summary                                    │
│  • transcript (Whisper / native captions if present)         │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ Judge Synthesizer (LLM or rules+LLM hybrid)                  │
│  Produces category scores, strengths, weaknesses, actions    │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ VideoQualityJudgeResult (canonical output)                   │
└──────────────────────────────────────────────────────────────┘
```

### 5.1 Recommended v1 mode: **Hybrid**

- **Deterministic floor** — scores cannot exceed integrity ceiling (e.g. no audio stream → `audio_score` capped at 20)
- **LLM synthesis** — strengths, weaknesses, `improvement_actions` from structured prompt with collected signals
- **Fail-safe** — if LLM unavailable, rules-only fallback with reduced confidence flag

---

## 6. Canonical Output Schema

**Version:** `video_quality_judge_v1`

```json
{
  "version": "video_quality_judge_v1",
  "run_id": "cb_e2e_20260616_225212_de9295da",
  "video_path": "outputs/runs/.../FINAL_BRANDED_VIDEO_CANONICAL.mp4",
  "provider": "runway",
  "audio_strategy": "narrator",
  "judged_at": "2026-06-16T22:55:00Z",
  "judge_mode": "hybrid",
  "overall_score": 72,
  "story_score": 68,
  "audio_score": 74,
  "visual_score": 71,
  "continuity_score": 65,
  "viral_score": 70,
  "category_details": {
    "story": { "beginning": 70, "middle": 65, "ending": 68, "pacing": 66 },
    "character": { "consistency": 62, "emotions": 70, "continuity": 65 },
    "audio": { "dialogue": 72, "environment": 78, "immersion": 71 },
    "visual": { "realism": 69, "motion": 73, "cinematic_feel": 70 },
    "viral": { "hook": 75, "retention": 68, "shareability": 67 }
  },
  "strengths": [
    "Environment ambience supports forest setting",
    "Opening hook aligns with planned curiosity gap"
  ],
  "weaknesses": [
    "Dialogue too weak in middle third",
    "Character visual drift between clips 2 and 3"
  ],
  "improvement_actions": [
    {
      "action_id": "boost_dialogue_emphasis",
      "target": "content_brain.dialogue_engine",
      "priority": "high",
      "reason": "dialogue too weak",
      "suggested_delta": { "dialogue_weight": +0.15 }
    },
    {
      "action_id": "increase_environment_weight",
      "target": "content_brain.environment_designer",
      "priority": "medium",
      "reason": "environment audio excellent",
      "suggested_delta": { "ambience_weight": +0.10 }
    }
  ],
  "threshold": {
    "pass_score": 70,
    "passed": true
  },
  "signals_used": ["ffprobe", "visual_continuity", "story_package", "llm_synthesis"],
  "confidence": 0.82
}
```

**User-facing simplified shape** (API / Results page):

```json
{
  "overall_score": 72,
  "story_score": 68,
  "audio_score": 74,
  "visual_score": 71,
  "continuity_score": 65,
  "viral_score": 70,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "improvement_actions": ["..."]
}
```

---

## 7. Persistence

Write under run metadata (Runway/Hailuo canonical run folder):

| File | Purpose |
|------|---------|
| `metadata/video_quality_judge.json` | Full result |
| `metadata/video_quality_judge_summary.json` | Slim API payload |

Kling runs:

| File | Purpose |
|------|---------|
| `outputs/kling_multishot_live/{run_id}/video_quality_judge.json` | Full result |

---

## 8. Results Page Integration (Future UI)

Add section **Video Judge** (after Delivery Truth, before Pipeline Status):

| UI element | Data |
|------------|------|
| Video Judge Score | `overall_score` / 100 |
| Overall Rating | `GREAT` ≥85 · `GOOD` ≥70 · `NEEDS WORK` ≥50 · `POOR` <50 |
| Category bars | story, audio, visual, continuity, viral |
| Strengths | bullet list |
| Weaknesses | bullet list |
| Improvement Suggestions | `improvement_actions` rendered as checklist |

**API:** extend `load_run_results()` / `ProductStudioService.get_results()` with:

```python
"video_quality_judge": { ... },
"video_judge_score": 72,
"video_judge_rating": "GOOD",
"improvement_suggestions": [...]
```

No new page — extend existing **Results** page only.

---

## 9. Thresholds & Modes

| Mode | Behavior |
|------|----------|
| **Advisory (v1 default)** | Judge always runs; results stored; learning loop optional |
| **Soft gate (v2)** | WARNING if `overall_score < 60`; upload_ready=false |
| **Hard gate (v3)** | FAIL publish if `overall_score < threshold` and channel enables `video_judge_hard_gate` |

Default threshold: **70** (configurable per channel profile).

---

## 10. Provider-Aware Judging

| Provider | Audio expectations | Visual expectations |
|----------|-------------------|---------------------|
| Runway + narrator | ElevenLabs dialogue audible, music optional | Multi-clip assembly, subtitle burn |
| Runway + music_only | No dialogue required | Visual loop / montage quality |
| Kling Native Audio | Native dialogue/ambience in clip | 2-shot continuity, native audio immersion |
| Hailuo | Same as Runway path when wired | Provider-specific motion cues |

Judge reads `audio_strategy` + `provider` from run metadata / preflight snapshot — **never** penalize Kling for missing ElevenLabs.

---

## 11. Long-Term Reference Library (Design Hook)

| Tier | Criteria | Storage (future) |
|------|----------|------------------|
| **Gold reference** | `overall_score ≥ 85` + delivery PASS | `project_brain/video_reference_library/gold/{run_id}/` |
| **Anti-pattern** | `overall_score < 50` OR repeated same weakness ≥3 runs | `project_brain/video_reference_library/anti/{run_id}/` |

Each entry stores: judge JSON, 3 keyframes, prompt snapshot, story_package hash — used as few-shot examples in Judge Synthesizer and Content Brain tuning.

---

## 12. Proposed Module Layout (Future Implementation)

```
content_brain/quality/
  video_quality_judge.py          # orchestrator
  video_quality_judge_models.py   # dataclasses + schema
  video_quality_signal_collectors.py
  video_quality_judge_synthesizer.py

project_brain/
  validate_video_quality_judge.py
  VIDEO_QUALITY_JUDGE_IMPLEMENTATION_REPORT.md
```

**Wire points:**

- `runway_live_post_processor.py` — post delivery gate hook (optional flag)
- `kling_product_run.py` — post generation hook
- `results_run_loader.py` — load judge JSON
- `product_studio_service.get_results()` — expose to UI

---

## 13. Implementation Phases (Recommended)

| Phase | Scope |
|-------|-------|
| **JUDGE-P0** | Schema + rules-only judge (ffprobe + existing reports) |
| **JUDGE-P1** | LLM synthesizer + improvement_actions |
| **JUDGE-P2** | Results page + API exposure |
| **JUDGE-P3** | Learning loop (see companion doc) |
| **JUDGE-P4** | Gold/anti reference library + few-shot tuning |

---

## 14. Open Questions

1. Should judge run on **assembled** or **branded** final MP4? **Recommendation:** branded canonical; fallback assembled.
2. Multimodal v1 — keyframes only vs full video upload to vision API? **Recommendation:** keyframe strip v1.1.
3. Hard gate default off until ≥20 judged runs calibrate thresholds per channel?

---

**Companion doc:** [`VIDEO_LEARNING_LOOP_DESIGN.md`](VIDEO_LEARNING_LOOP_DESIGN.md)

**Related docs:**

- [`DELIVERY_QUALITY_GATE_DESIGN.md`](DELIVERY_QUALITY_GATE_DESIGN.md) — integrity vs quality
- [`KLING_FULL_PRODUCT_INTEGRATION_REPORT.md`](KLING_FULL_PRODUCT_INTEGRATION_REPORT.md) — Kling metadata inputs
- `content_brain/execution/content_brain_quality_audit_v2.py` — pre-run audit
