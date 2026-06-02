# Phase 12A — User Acceptance Test (UAT) Runtime Design

**Status:** Design only — no implementation, no new architecture layers  
**Date:** 2026-06-01  
**Prerequisites:** Content Brain, Video/Voice/Subtitle/Assembly runtimes complete; real ElevenLabs smoke (11H-2e) and real FFmpeg assembly smoke (11J-19) passed  
**Next phase:** **PHASE 12B — UAT Runtime Implementation** (requires separate operator approval before any paid provider or real assembly run)

---

## Explicit Approval Boundary

> **This design does NOT authorize production mode, batch generation, or autonomous publishing.**

Phase 12A defines a **single-topic, single-video, human-review workflow**. It composes existing runtimes behind one operator-facing entry point. No new engines, orchestrators, or provider adapters are required for the design.

Implementation (12B+) must preserve:

- Fail-closed defaults for all real execution paths  
- Per-stage operator approval where already required (voice live TTS, assembly real FFmpeg)  
- One active UAT run at a time  
- No queue batching, no auto-publish, no content factory behavior  

---

## Problem Statement

Architecture and smoke tests confirm that each runtime **can** execute in isolation:

| Layer | Validated by |
|-------|----------------|
| Content Brain → story | 11X topic→voice dry run, Content Brief orchestrator |
| Video Runtime | Runway/Hailuo hardening phases (11E, 11F) |
| Voice Runtime | 11H-2e real ElevenLabs smoke |
| Subtitle Runtime | 11I-8 API validation |
| Assembly Runtime | 11J-19 real FFmpeg smoke → `FINAL_PUBLISH_READY.mp4` |

What is **not** validated:

- Story quality as a viewer would perceive it  
- Visual quality, clip continuity, pacing  
- Voice naturalness, pronunciation, emotional fit  
- Subtitle readability, timing, burn-in aesthetics  
- Overall “would I publish this?” judgment  

**AI validators cannot reliably score these.** Only the operator/user can.

Phase 12A exists to close that gap with a **User Acceptance Test mode**: one real topic in, one real final video out, human scores out.

---

## Phase 12A Objective

**Do not build more architecture first.**

Validate one question:

> Can a real user provide a topic and receive a video they would actually consider publishing?

The answer — captured in structured human reviews — determines whether the next investment goes to story, video, voice, subtitle, assembly, continuity, or trend discovery.

---

## UAT Mode Definition

| Property | UAT mode | Production mode (out of scope) |
|----------|----------|--------------------------------|
| Topics per run | **1** | Many |
| Sessions per run | **1** | Batch / queue |
| Publishing | **Never** | Auto or scheduled |
| Autonomy | **Operator-supervised** | Autonomous factory |
| Purpose | Human quality review | Scale and revenue |
| Output | `FINAL_PUBLISH_READY.mp4` + review form | CDN / platform upload |

---

## End-to-End UAT Flow

```
Operator
  → UAT Entry (UI or supervised CLI)
      → Inputs: topic, platform, duration, provider preferences
      → Create session: exec_uat_{timestamp}
      ↓
[1] Content Brain
      ContentBriefOrchestrator.run(topic, platform, duration, ...)
      → brief_snapshot on session (story architecture, beats, clip plan)
      ↓
[2] Session population
      SessionPopulationBuilder + SessionNarrationAdapter
      → execution_runtime shell, narration segments, video prompts
      ↓
[3] Video Runtime  (Runway Browser — default UAT)
      ProviderRuntimeEngine / RunwayBrowserOrchestrator
      → clip_*.mp4 under video_generation/
      ↓
[4] Voice Runtime  (ElevenLabs — default UAT)
      Preflight → approve → VoiceRunService (live, confirm_live_tts)
      → narration_*.mp3 under voice_generation/
      ↓
[5] Subtitle Runtime
      POST /subtitle/run → subtitles.ass under subtitle_generation/
      ↓
[6] Assembly Runtime
      assembly dry-run → assembly approve → assembly real run (gated)
      → FINAL_PUBLISH_READY.mp4 + assembly_manifest.json
      ↓
[7] UAT completion
      → runtime report written
      → artifact folder path surfaced
      → optional: open folder
      → user review form presented
      ↓
[8] Review storage
      → project_brain/user_acceptance_reviews/{session_id}_review.json
```

### Example input

| Field | Example |
|-------|---------|
| Topic | Cat in the streets of Los Angeles |
| Platform | YouTube Shorts |
| Target duration | 45 seconds |
| Video provider | Runway Browser |
| Voice provider | ElevenLabs (live) |
| Subtitle mode | burn-in ASS |
| Assembly | Assembly Runtime (local FFmpeg) |

---

## Composition Strategy (No New Architecture)

UAT is a **thin orchestration shell** over existing systems. Do **not** create parallel pipelines or import `pipelines/full_video_pipeline.py`.

| Step | Reuse (existing) | Notes |
|------|------------------|-------|
| Content Brain | `ContentBriefOrchestrator`, `ContentBriefRunRequest` | Same as `ui/components/content_brain_panel.py` / 11X runner |
| Session seed | `SessionPopulationBuilder`, `SessionNarrationAdapter`, `ExecutionSessionStore` | Pattern from `run_11x_end_to_end_topic_to_voice_dry_run.py` |
| Governance | `SimulationReportBuilder`, `ApprovalBudgetGovernanceEngine`, `ExecutionReadinessGate` | Optional enrich before video dispatch |
| Video | `ProviderRuntimeEngine` + `RunwayBrowserOrchestrator` | Browser mode default for UAT; operator present |
| Voice | `VoiceRunService`, approval write APIs, env flags scoped to run | Mirror `run_11h2e_supervised_smoke_test.py` but multi-segment allowed within UAT caps |
| Subtitle | `SubtitleRunService` / `POST /subtitle/run` | Real generation per 11I |
| Assembly | `AssemblyRunService`, approval APIs, env flags scoped to run | Mirror `run_11j19_supervised_assembly_smoke_test.py` with UAT profile (not smoke caps) |
| Observability | Execution Center panels (`RuntimeObservability`, category slots) | Session drawer shows stage progress |

**Proposed new files (12B only — listed here for design clarity):**

| File | Role |
|------|------|
| `content_brain/execution/uat_runtime_profile.py` | UAT caps (duration, clip count, cost ceiling) — distinct from smoke profiles |
| `project_brain/run_12b_uat_supervised_pipeline.py` | Supervised CLI runner (primary 12B entry for first runs) |
| `ui/web/src/pages/UatRuntimePage.tsx` | Operator UI wizard (12C optional if CLI-first) |
| `ui/api/uat_runtime_service.py` | Backend coordinator (thin; delegates to existing services) |
| `project_brain/user_acceptance_reviews/` | Review JSON storage directory |

---

## UI Entry Point (Design)

### Recommended: UAT tab in Execution Center (React)

Current nav (`ui/web/src/App.tsx`) shows **Execution Center** active; Content Brain / Story Studio disabled. UAT should **not** re-enable legacy tkinter Content Brain panel as the primary path.

**Proposed nav item:** `User Acceptance Test` (or `UAT Runtime`) — enabled, sibling to Execution Center.

**UAT page sections:**

1. **Inputs** — topic (required), platform dropdown, duration slider (15–90s for UAT v1), provider pickers  
2. **Preflight summary** — estimated clips, narration length, rough cost (read-only from governance engines)  
3. **Run controls** — single **Start UAT Run** button; disabled while a run is active  
4. **Progress** — stage checklist: Brain ✓ → Video → Voice → Subtitle → Assembly → Done  
5. **Outputs** — session ID, report link, artifact path, **Open folder** button, **Play final video** (local file URL or embedded player)  
6. **Review form** — scores 0–10 + comments (see Review Workflow)  

### Alternate: Supervised CLI first (12B)

Mirror smoke-test pattern before UI:

```bash
python -m project_brain.run_12b_uat_supervised_pipeline \
  --topic "Cat in the streets of Los Angeles" \
  --platform youtube_shorts \
  --duration 45
```

CLI prints session ID, paths, and prompts operator to complete review template manually or via a follow-up command:

```bash
python -m project_brain.submit_uat_review --session-id exec_uat_...
```

**Recommendation:** Ship **CLI-first in 12B**, UI wizard in **12C**, after one successful supervised UAT run.

---

## Session Lifecycle

| Phase | Session prefix | `execution_session_id` example |
|-------|----------------|--------------------------------|
| UAT run | `exec_uat_` | `exec_uat_20260601_160000` |

**Session metadata flags (proposed on `execution_runtime.operations`):**

```json
{
  "uat_run": {
    "mode": "user_acceptance_test",
    "topic": "Cat in the streets of Los Angeles",
    "platform": "youtube_shorts",
    "target_duration_seconds": 45,
    "started_at": "...",
    "completed_at": null,
    "status": "running",
    "triggered_by": "operator_uat",
    "providers": {
      "video": "runway_browser",
      "voice": "live_elevenlabs",
      "subtitle": "local_subtitle_runtime",
      "assembly": "local_assembly_runtime"
    }
  }
}
```

**Rules:**

- One `running` UAT session globally (policy block if another active)  
- Session is **not** reused for a second topic  
- Failed UAT runs keep artifacts for forensics; operator may abandon or retry with **new** session  

---

## Output Locations

All artifacts remain under the standard execution store (no legacy folders):

```
storage/content_brain/execution/
  sessions/{session_id}.json
  artifacts/{session_id}/
    video_generation/
      clip_001.mp4 … clip_N.mp4
      video_manifest.json
    voice_generation/
      narration_001.mp3 …
      voice_manifest.json
    subtitle_generation/
      subtitles.ass
      subtitle_manifest.json
    assembly_generation/
      FINAL_PUBLISH_READY.mp4      ← primary UAT deliverable
      assembly_manifest.json
  runtime/
    jobs/ …
    audit.jsonl
```

**UAT runtime report (written at completion):**

```
project_brain/PHASE_12B_UAT_RUN_{session_id}_REPORT.md
```

or consolidated:

```
project_brain/uat_runs/{session_id}_runtime_report.md
```

**Completion payload (API / CLI):**

| Field | Example |
|-------|---------|
| `session_id` | `exec_uat_20260601_160000` |
| `artifact_folder` | `…/artifacts/exec_uat_20260601_160000/` |
| `final_video_path` | `…/assembly_generation/FINAL_PUBLISH_READY.mp4` |
| `runtime_report_path` | `project_brain/uat_runs/…` |
| `review_submitted` | `false` until operator saves review |

**Optional: open artifact folder**

- Windows: `os.startfile(artifact_folder)` from CLI runner (operator opt-in flag `--open-folder`)  
- UI: `shell.openPath` equivalent via backend endpoint `POST /uat/runs/{id}/open-artifacts` (desktop-only, safe)  

---

## Stage Gates and Operator Checkpoints

UAT is supervised, not fully autonomous. Design includes **pause points** where the operator confirms continuation (especially before spend).

| Stage | Gate | Real execution flags |
|-------|------|----------------------|
| Content Brain | None (local LLM / trend APIs only) | — |
| Video | Browser session ready; Runway login | Existing browser orchestrator |
| Voice | `POST /voice/approve` + `confirm_live_tts=true` | `MODIR_VOICE_LIVE_TTS_ENABLED`, `LIVE_RUNTIME_EXECUTION_APPROVED` scoped to run |
| Subtitle | Preflight READY | Per 11I policy (no extra env in current design) |
| Assembly | Dry-run → `POST /assembly/approve` → real run | `MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED`, `ASSEMBLY_RUNTIME_EXECUTION_APPROVED` scoped to run |

**12B default:** CLI runner auto-approves within UAT caps after printing cost estimate; operator must pass `--i-understand-real-providers` (same pattern as smoke tests).

**12C UI default:** Explicit confirm dialog before voice and assembly real execution.

---

## UAT Safety Limits (Not Smoke Caps)

Distinct from 11H-2e / 11J-19 smoke profiles. UAT allows a **realistic short** but still bounded.

| Limit | UAT v1 value | Rationale |
|-------|--------------|-----------|
| Concurrent UAT runs | **1** | Operator supervision |
| Topics per run | **1** | Single acceptance decision |
| Target duration | **15–90 s** | Shorts/reels realistic band |
| Max clips | **6** | Align with typical brief clip count |
| Max voice segments | **8** | Match beat/narration plan |
| Max estimated voice cost | **$1.00** (configurable) | Prevent runaway TTS spend |
| Max assembly output size | **50 MB** | Sanity cap for local FFmpeg |
| Assembly timeout | **300 s** | Longer than smoke; still bounded |
| Batch / queue | **Forbidden** | No `ExecutionQueueEngine` batch dispatch in UAT |
| Auto-publish | **Forbidden** | No YouTube/TikTok upload APIs |
| `full_video_pipeline.py` | **Forbidden** | Use runtime composition only |

Proposed module: `content_brain/execution/uat_runtime_profile.py` with `evaluate_uat_runtime_caps(session, request)`.

---

## Failure Handling

| Failure | Behavior |
|---------|----------|
| Content Brain rejects brief | Stop; no session spend; report reason |
| Video clip partial / failed | Stop or offer “continue with N clips” (operator choice); never silent continue |
| Voice TTS failed | Stop; preserve partial MP3s; flags disabled in `finally` |
| Subtitle failed | Stop before assembly; upstream artifacts preserved |
| Assembly failed | Stop; partial `_work/` preserved; flags disabled |
| Operator cancel | `operations_control.cancel_requested`; stages fail-closed |
| Retry | **New session only** — no in-place retry loop |

UAT runner writes `status=failed` on `operations.uat_run` with mapped failure code from existing taxonomies.

---

## User Review Workflow

After `FINAL_PUBLISH_READY.mp4` exists, the operator watches the video and completes a review.

### Review template (scores 0–10)

| Dimension | Question |
|-----------|------------|
| Story Quality | Does the narrative hook, build, and payoff work for the topic? |
| Visual Quality | Are clips usable, on-brand, and sharp enough to publish? |
| Voice Quality | Is narration natural, clear, and well-paced? |
| Subtitle Quality | Are subtitles readable, timed correctly, and not distracting? |
| Clip Continuity | Do clips feel connected, or jarring / unrelated? |
| Overall Quality | Would you publish this video as-is? |

**Comments (free text):**

- What felt good?  
- What felt wrong?  
- What should improve?  

### Review storage

**Directory:** `project_brain/user_acceptance_reviews/`

**Filename:** `{session_id}_review.json`

**Schema:**

```json
{
  "review_version": "12a_v1",
  "session_id": "exec_uat_20260601_160000",
  "submitted_at": "2026-06-01T17:30:00Z",
  "submitted_by": "operator",
  "uat_inputs": {
    "topic": "Cat in the streets of Los Angeles",
    "platform": "youtube_shorts",
    "target_duration_seconds": 45,
    "providers": {
      "video": "runway_browser",
      "voice": "live_elevenlabs",
      "subtitle": "local_subtitle_runtime",
      "assembly": "local_assembly_runtime"
    }
  },
  "artifact_paths": {
    "final_video": "storage/content_brain/execution/artifacts/.../FINAL_PUBLISH_READY.mp4",
    "artifact_folder": "storage/content_brain/execution/artifacts/exec_uat_..."
  },
  "scores": {
    "story_quality": 7,
    "visual_quality": 6,
    "voice_quality": 8,
    "subtitle_quality": 7,
    "clip_continuity": 5,
    "overall_quality": 6
  },
  "comments": {
    "felt_good": "Voice tone matched the mood; hook narration was strong.",
    "felt_wrong": "Clip 3 looked unrelated; subtitles slightly late on beat 4.",
    "should_improve": "Better visual continuity between clips; tighten escalation beat."
  },
  "publish_would_you": false,
  "runtime_report_path": "project_brain/uat_runs/exec_uat_20260601_160000_runtime_report.md"
}
```

**Optional aggregate index:** `project_brain/user_acceptance_reviews/index.jsonl` — one line per review for trend analysis across UAT runs.

**API (12C):** `POST /uat/reviews` with body matching schema; `GET /uat/reviews/{session_id}`.

---

## Runtime Report Contents

Each UAT run produces a human-readable report for the operator and for future phase planning.

**Include:**

- Session ID, topic, platform, duration, providers  
- Content Brief decision + clip/beat summary  
- Per-stage status and duration  
- Artifact paths (no secrets, no API keys)  
- Cost telemetry summary (voice estimate vs actual if available)  
- Final video path and file size  
- Link to review file (once submitted)  
- Explicit **“NOT PUBLISHED”** banner  

**Exclude:** Raw API keys, full narration text dumps (use previews only), provider cookies.

---

## Success Criteria (Phase 12A Design Acceptance)

Design is accepted when it clearly enables:

| # | Criterion |
|---|-----------|
| 1 | Operator can enter topic + platform + duration + provider preferences |
| 2 | One session produces one `FINAL_PUBLISH_READY.mp4` via existing runtimes |
| 3 | Outputs are locatable: session ID, artifact folder, final MP4 path, runtime report |
| 4 | Operator can score quality on 6 dimensions + free-text comments |
| 5 | Reviews persist under `project_brain/user_acceptance_reviews/` |
| 6 | No batch mode, no auto-publish, no autonomous factory |
| 7 | No new architecture layers — composition only |
| 8 | Safety limits and approval gates documented per stage |

**Phase 12B implementation success** (future): at least **one** complete UAT run from real topic to reviewed output.

---

## What Phase 12A / 12B Does NOT Include

| Out of scope | Reason |
|--------------|--------|
| Batch topic queue | Contradicts UAT purpose |
| Auto YouTube/TikTok upload | Publishing is separate product decision |
| Autonomous content factory | Requires validated human quality first |
| New story/video/voice/subtitle engines | Optimize after UAT feedback |
| Production-scale queue worker changes | Premature |
| Replacing approval gates with auto-approve globally | Safety regression |
| AI-based quality scoring as gate | Unreliable for acceptance decisions |
| `full_video_pipeline.py` | Legacy monolith; forbidden by runtime architecture rules |

---

## Decision Framework After UAT Runs

After **3–5** UAT runs with stored reviews, prioritize based on **lowest median scores** and recurring comment themes:

```
IF median(clip_continuity) < 6  → invest in video prompt continuity / clip planning
IF median(voice_quality) < 6    → invest in narration adapter / TTS settings
IF median(story_quality) < 6    → invest in story architecture / hook engine
IF median(subtitle_quality) < 6 → invest in cue timing / ASS styling
IF median(visual_quality) < 6   → invest in Runway prompt / reference frames
IF median(overall) >= 8         → consider limited beta (still not batch factory)
```

This framework is **documentation only** in 12A; automation of prioritization is out of scope.

---

## Implementation Roadmap (Post-Design)

| Phase | Deliverable | Real providers? |
|-------|-------------|-----------------|
| **12A** | This design doc | No |
| **12B** | Supervised CLI UAT runner + review submit CLI + caps module | Yes — operator-approved |
| **12C** | UAT UI page + review form + progress checklist | Yes |
| **12D** | UAT validation matrix + regression guards | Mock + one manual UAT |
| **12E** | Post-UAT analysis report template across reviews | No |

**Do not start 12B until operator explicitly approves** implementation and understands per-run provider cost exposure.

---

## References (Existing Code)

| Area | Path |
|------|------|
| Content Brain orchestrator | `content_brain/orchestrators/content_brief_orchestrator.py` |
| Topic→voice dry run | `project_brain/run_11x_end_to_end_topic_to_voice_dry_run.py` |
| Voice smoke pattern | `project_brain/run_11h2e_supervised_smoke_test.py` |
| Assembly smoke pattern | `project_brain/run_11j19_supervised_assembly_smoke_test.py` |
| Session store / artifacts | `content_brain/execution/session_store.py` |
| Video dispatch | `content_brain/execution/provider_runtime_engine.py` |
| Runway browser | `orchestrators/runway_browser_orchestrator.py` |
| Voice API | `ui/api/voice_run_service.py` |
| Subtitle API | `ui/api/main.py` → `/subtitle/run` |
| Assembly API | `ui/api/assembly_run_service.py` |
| Execution Center UI | `ui/web/src/pages/ExecutionCenterPage.tsx` |
| Legacy Content Brain UI | `ui/components/content_brain_panel.py` (reference only) |

---

## Confirmation Checklist (Design Phase)

| Requirement | Design status |
|-------------|---------------|
| Runtime flow documented | Yes |
| UI entry point specified | Yes (CLI-first + UAT page) |
| Output locations documented | Yes |
| Review workflow + template | Yes |
| Review storage path + schema | Yes |
| Safety limits documented | Yes |
| Success criteria defined | Yes |
| No implementation in 12A | Yes |
| No batch / no auto-publish | Yes |
| Composition over new architecture | Yes |

---

**Phase 12A design complete.** Next step: operator review of this document, then explicit approval for **PHASE 12B — UAT Runtime Implementation**.
