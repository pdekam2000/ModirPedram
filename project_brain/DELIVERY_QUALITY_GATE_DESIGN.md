# Delivery Quality Gate Design

**Phase:** DELIVERY-QUALITY-RECOVERY — Priority 6  
**Mode:** Design only — no implementation  

---

## Problem statement

Today `publish_completed` / `status: completed` can be reached when:

- Final video duration << assembled duration
- Subtitles enabled but not visible in deliverable
- Music enabled in product intent but not merged
- Character dialogue planned but not audible
- Branding reports `failed` then overwritten to `completed`

**Goal:** Separate **runtime completion** (steps executed) from **delivery quality PASS** (publishable artifact).

---

## Gate placement

Proposed single gate: **`evaluate_delivery_quality()`** immediately before:

1. `write_runway_phase_i_checkpoint(..., checkpoint=publish_completed)`
2. `promote_canonical_final_video()` / registry update
3. UI “SUCCESS” / upload-ready flags

**Location:** `content_brain/execution/runway_live_post_processor.py` (or `content_brain/platform/delivery_quality_gate.py` called from there).

**Fail closed:** If gate = FAIL → checkpoint `publish_blocked`, no canonical promotion, UI shows FAILED with reasons.

---

## Inputs (manifests + ffprobe)

| Source | Fields |
|--------|--------|
| `assembly_manifest` | `output_path`, `clip_count`, `status` |
| `audio_post_result` | `narrated_video_path`, `duration_seconds`, `music_status_code`, `character_voice_status`, warnings |
| `branding_post_result` | `final_branded_video_path`, `steps.subtitles`, `status`, warnings |
| `publish_manifest` | paths, metadata |
| **ffprobe** | duration, audio stream count, mean volume (optional) |
| **Channel profile** | `subtitle_enabled`, `music_provider`, `character_voice_mode`, `branding_enabled` |

---

## PASS conditions (all required for PASS)

| ID | Check | Rule |
|----|-------|------|
| P1 | Assembly ready | `assembly_status == ASSEMBLED` |
| P2 | **Duration preservation** | `duration(branded) >= duration(assembled) - 0.5s` |
| P3 | Audio present | Branded file has ≥1 audio stream with mean volume > −45 dB |
| P4 | Narration merged | `narrated_video_path` exists and was consumed |
| P5 | Subtitles (if enabled) | `branding.steps.subtitles.status == PASS` AND `burn_visible_enough == true` |
| P6 | Music (if enabled) | `music_provider != none` → `music_runtime.status == completed` AND `audibility_pass == true` |
| P7 | Character voices (if enabled) | `character_voice_mode == multi_voice` AND story package has >1 character → audible dialogue OR explicit `narrator_only` mode |
| P8 | Canonical file exists | `FINAL_BRANDED_VIDEO_CANONICAL.mp4` size > 100 KB |
| P9 | Topic authority | story package topic == authoritative topic (optional hard gate) |
| P10 | No truncate warning | `duration(assembled) / clip_count ≈ 10s` within tolerance |

---

## WARNING conditions (publish allowed with flag, not upload-ready)

| ID | Check | Rule |
|----|-------|------|
| W1 | Logo skipped | `logo.status == SKIP` (logo_missing) |
| W2 | Low ambience audibility | Env mix PASS but mean volume < −38 dB |
| W3 | Story score / audit warnings | story_audio_audit warnings non-empty |
| W4 | Visual continuity warnings | non-blocking |
| W5 | Duplicate narration segments | segments 3–4 identical text |
| W6 | Music skipped intentionally | `music_provider == none` but user expects music → WARNING not FAIL |
| W7 | Branding status was `failed` then completed | log contradiction |

**WARNING behavior:** `delivery_status: WARNING`, file published to `publish/` but `upload_ready: false`.

---

## FAIL conditions (block canonical promotion)

| ID | Check | Rule |
|----|-------|------|
| F1 | Duration truncation | `duration(branded) < duration(assembled) - 0.5s` |
| F2 | Subtitle enabled + burn failed | `subtitle_enabled` and not P5 |
| F3 | Missing audio | no audio stream on branded file |
| F4 | Assembly failed | `assembly_status != ASSEMBLED` |
| F5 | Branded file missing | canonical path absent or empty |
| F6 | Music required but failed | profile music enabled AND merge/audibility failed |
| F7 | Narration merge failed | `audio_post.status == merge_failed` |
| F8 | Topic drift (optional strict) | story package genre/cast contradicts authoritative topic |

---

## Status model (proposed)

```json
{
  "delivery_quality_version": "delivery_quality_gate_v1",
  "delivery_status": "PASS | WARNING | FAIL",
  "runtime_status": "completed",
  "upload_ready": true,
  "checks": [
    {"id": "P2", "name": "duration_preservation", "passed": false, "detail": "18.46s < 40.17s"}
  ],
  "failures": ["F1"],
  "warnings": ["W2"],
  "canonical_video_path": "...",
  "assembled_duration_seconds": 40.17,
  "deliverable_duration_seconds": 18.46
}
```

---

## Checkpoint behavior change (design)

| Current | Proposed |
|---------|----------|
| `publish_completed` on any publish manifest | `publish_completed` only if `delivery_status == PASS` |
| `latest_run_attempt.status: completed` | `completed` = runtime; add `delivery_status` field |
| UI SUCCESS on `run_ok` | UI SUCCESS only on `delivery_status == PASS` |

---

## Profile-aware rules

| Setting | FAIL if | WARNING if | PASS if |
|---------|---------|------------|---------|
| `subtitle_enabled: true` | burn not visible | PSNR low but visible | burn visible |
| `music_provider: none` | — | user expects music | skip check |
| `music_provider: local` | merge/audibility fail | quiet mix | audibility_pass |
| `character_voice_mode: multi_voice` | dialogue planned, 0 voice clips | narrator-only fallback | multi-voice merged |
| `branding_enabled: false` | — | — | skip subtitle/logo/CTA checks |

---

## Observability

Write gate result to:

- `outputs/runs/{run}/metadata/delivery_quality_gate.json`
- `project_brain/runtime_state/delivery_quality_gate.json` (latest)
- Include in `publish/metadata.json` as `delivery_quality` block

---

## Non-goals (this design)

- No new providers
- No new pipeline stages
- No prompt/story redesign
- Gate evaluates existing artifacts only

**Implementation awaits approval after architecture review.**
