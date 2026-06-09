# Phase I — Clip 2 Failure Diagnostic

**Phase:** RUNWAY-STARTER-TO-VIDEO-I (3-clip live smoke)  
**Diagnostic date:** 2026-06-07  
**Mode:** Read-only analysis — no code changes  
**Primary artifacts:**
- `project_brain/runway_phase_i_3clip_last_report.json`
- `project_brain/PHASE_RUNWAY_STARTER_TO_VIDEO_I_3CLIP_LIVE_REPORT.md`
- `project_brain/runway_phase_i_completion_gate_diagnostics.json`
- `project_brain/runway_live_smoke_artifacts/` (screenshots)

**Secondary artifact (stale — not this run):**
- `project_brain/runway_phase_i_last_failure_diagnostics.json` (timestamp **2026-06-04**, `error: "test"`, step `021_verify_use_frame_handoff_clip_2`)

---

## Executive summary

The run **did stop before Clip 2**, but the **exact failure point was Clip 1 strict completion**, not Clip 2 Use Frame or Clip 2 prompt prep.

| Operator observation | Runtime evidence |
|---------------------|------------------|
| Starter image succeeded | Confirmed — steps 001–012 completed; image card `554\|296\|476\|853\|` selected; Use to Video OK |
| Clip 1 succeeded (visual) | **Not confirmed by runtime** — Clip 1 generate was approved and clicked, but strict completion gate never released |
| Stopped before Clip 2 | **Confirmed** — runtime never reached step `020_use_frame_for_clip_2` or any Clip 2 step |

**Failure step:** `017_wait_until_completion_signal_clip_1`  
**Failure type:** 25-minute strict completion timeout while gate still saw `generation_in_progress`  
**Clip 2 chain:** Never entered (no download, no Use Frame, no Clip 2 prompt fill, no Clip 2 generate gate)

---

## Run identity

| Field | Value |
|-------|-------|
| Project | `phase_i_live` |
| Started | 2026-06-07 15:44:08 |
| Finished | 2026-06-07 16:33:25 (~49 min total) |
| Result | `ok: false` |
| Content Brain handoff | `CONTENT_BRAIN_V83` (`cb_e2e_20260607_152349_e2c0b30b`) |
| Page URL (last) | `https://app.runwayml.com/video-tools/teams/kamangarpedram/ai-tools/generate?mode=tools&tool=video&sessionId=5920152d-ba9d-4d74-81c0-534f4b43486c` |

---

## Step plan reference (37 steps)

| Step | Step ID | Phase |
|------|---------|-------|
| 001–012 | Starter image → Use to Video | starter_image |
| 013–017 | Clip 1 prompt → generate → **wait completion** | clip_1 |
| 018–019 | Clip 1 download → settle | clip_1 |
| **020–022** | **Use Frame → settle → verify handoff** | **clip_2** |
| 023–026 | Clip 2 prompt → generate → wait | clip_2 |
| 027+ | Clip 2 download → Clip 3 chain | clip_2 / clip_3 |

---

## Exact step reached / failed

### Last step successfully executed

| Step | ID | Evidence |
|------|-----|----------|
| 016 | `016_video_generate_manual_required_clip_1` | Approval granted 2026-06-07 16:07:37; action log `click generate_button` (approved) |
| (implicit) | Clip 1 prompt filled | `fill_prompt` `chars=1483; selector=div[aria-label="Prompt"]` |
| (implicit) | Video settings | `video_settings_verify_ok` aspect=9:16 duration=10s |

### Step entered then failed

| Step | ID | Duration | Outcome |
|------|-----|----------|---------|
| **017** | **`017_wait_until_completion_signal_clip_1`** | ~25 min (16:07 → ~16:33) | **TimeoutError** |

### First Clip 2 step never reached

| Step | ID | Status |
|------|-----|--------|
| 018 | `018_download_mp4_clip_1` | Not reached |
| 020 | `020_use_frame_for_clip_2` | Not reached |
| 023 | `023_video_prompt_clip_2` | Not reached |
| 025 | `025_video_generate_manual_required_clip_2` | Not reached |

---

## Exception / stop condition

### Reported error (authoritative)

```
step failed at 017_wait_until_completion_signal_clip_1: strict clip completion not detected within 25 minutes for clip 1 (last_reason=generation_in_progress)
```

### Underlying exception (from semi-auto engine)

```
TimeoutError: strict clip completion not detected within 25 minutes for clip 1 (last_reason=generation_in_progress)
```

### Runtime state snapshot (from report)

| Field | Value |
|-------|-------|
| `ok` | `false` |
| `final_status` | `""` (empty — run aborted in `except` before copy; session was internally `FAILED`) |
| `stopped_reason` | See error above |
| `clips_completed` | `0` |
| `clip_1_completion_verified` | `false` |
| `clip_1_completion_reason` | `""` |
| `video_completion_detected` | `false` |
| `completion_signals` | `[]` |
| `approvals_granted` | 2 (image generate + clip 1 video generate only) |
| `video_generates_approved_count` | `0` (report counter; 1 generate was actually approved in approvals list) |
| `artifact_card_assignments` | `{}` (empty) |
| `use_frame_last_frame_by_clip` | `{}` (empty) |

### Strict completion gate at timeout

Source: `project_brain/runway_phase_i_completion_gate_diagnostics.json` (timestamp **2026-06-07 16:32:55**, context `timeout`)

| Field | Value |
|-------|-------|
| `clip_index` | 1 |
| `complete` | `false` |
| `reason` | `generation_in_progress` |
| `generation_in_progress` | `true` |
| `stop_cancel_visible` | `true` |
| `spinner_visible` | `false` |
| `artifact_cards` | `[]` |
| `assigned_card_fingerprint` | `""` |
| `completed_card_fingerprint` | `""` |
| `download_button_candidates` | `[]` |
| `use_frame_candidates` | `[]` |
| `progress_text` | `"Get notifications when your generations are complete. Don't show again Later Enable"` (notification banner text — possible false signal) |

**Interpretation:** At timeout the gate still treated Clip 1 as generating (`stop_cancel_visible: true`). No artifact cards were visible to the tracker (`artifact_cards: []`), and no assigned fingerprint was recorded in the gate despite repeated `latest_video_card_assigned` log lines during polling.

---

## Checklist (7 items)

### 1. Did `latest_video_card` get assigned?

**Partially — log says yes; gate/tracker say no effective assignment.**

| Source | Clip 1 assignment |
|--------|-------------------|
| Action log | **Yes** — many `latest_video_card_assigned` entries with `clip=1` |
| Report `artifact_card_assignments` | **No** — `{}` |
| Completion gate `assigned_card_fingerprint` | **No** — `""` at timeout |
| `artifact_cards` scan at timeout | **No** — `[]` |

**Latest video card fingerprint (from action log, repeated during wait):**

```
488|-247|608|439|video|gen-4_5 - continuity lock same character (an old man), same wardrobe, same location (quiet beach at apps use frame edit
```

**Red flags:**
- Negative Y coordinate (`-247`) suggests off-screen / stale DOM card
- Fingerprint text references **prior run content** (“an old man”, “quiet beach”) — **not** the Content Brain perfume run
- Does **not** match Clip 1 prompt filled in this run (fragrance entrepreneur / 1483 chars)

**Starter image card (separate, succeeded):**

```
554|296|476|853|
```

---

### 2. Did `prepare_last_frame_use_frame_for_clip()` run?

**No.**

- No action log entries for last-frame seek / prepare use frame
- No steps `020_use_frame_for_clip_2` or later executed
- `use_frame_last_frame_by_clip` report field is `{}`
- Function is invoked from step `020_use_frame_for_clip_2` in `runway_continuity_semi_auto.py` — that step was never reached because Clip 1 never passed strict completion / download

---

### 3. Did Use Frame button become visible?

**Not evaluated for Clip 2 handoff (Clip 2 never started).**

At Clip 1 completion timeout:
- `use_frame_candidates`: `[]`
- `use_frame_button_visible` in stale 2026-06-04 failure file: `true` (simulate run — **not this live run**)

For this live run, Use Frame visibility for Clip 2 was **never checked**.

---

### 4. Did Use Frame click execute?

**No.**

- No `click` on `use_frame_button` in this run’s action log
- `use_frame_after_clips`: `[]`
- `clip_2_use_frame_handoff_checked`: `false`

---

### 5. Did Clip 2 prompt get prepared?

**No.**

| Field | Value |
|-------|-------|
| `clip_2_prompt_ready_checked` | `false` |
| `clip_2_prompt_ready_result` | `""` |
| Action log `fill_prompt` for clip 2 | **Absent** |
| Step `023_video_prompt_clip_2` | **Not reached** |

Clip 2 prompt existed **only in the continuity plan** (continuity_notes show `clip_2_continuity_lock=present`), but was **never written to the Runway prompt editor**.

---

### 6. Did Clip 2 generation gate get requested?

**No.**

| Expected gate | Step | Status |
|---------------|------|--------|
| Clip 2 video generate approval | `025_video_generate_manual_required_clip_2` | Never reached |
| Approvals in report | Only image + **clip 1** generate | 2 total |

No operator approval was requested for Clip 2 generate.

---

### 7. What exact exception or stop condition set runtime status = FAILED?

| Layer | Value |
|-------|-------|
| Session status (internal) | `SEMI_AUTO_STATUS_FAILED` (set in `advance()` on TimeoutError) |
| Report `final_status` | `""` (not copied — exception path) |
| Report `stopped_reason` | `step failed at 017_wait_until_completion_signal_clip_1: strict clip completion not detected within 25 minutes for clip 1 (last_reason=generation_in_progress)` |
| Root cause | Strict completion gate polled ~25 min; last evaluation `reason=generation_in_progress`, `stop_cancel_visible=true`, no completed video card detected |
| Secondary warnings | Screenshot timeouts during pending polls; story progression audit weak separation |

---

## Timeline (Clip 1 → failure)

| Time | Event |
|------|-------|
| 15:44:08 | Run started |
| 15:49:38 | Image generate approved |
| ~15:50+ | Image ready manual hold → ready |
| ~16:04+ | Use to Video; transition to video tool verified |
| ~16:07 | Clip 1 prompt filled (1483 chars); duration set 10s |
| 16:07:37 | Clip 1 video generate approved + clicked |
| 16:07–16:32 | Step 017 polling — 27+ `strict_completion_pending_clip_1` screenshots |
| 16:32:55 | Completion gate diagnostics written (`context: timeout`) |
| 16:33:25 | Run finished FAIL |

**Elapsed on step 017:** ~25 minutes (matches `MAX_COMPLETION_WAIT_MINUTES = 25`)

---

## Why it *looked* like “Clip 1 succeeded” but stopped before Clip 2

1. **Operator side:** Runway may have shown a finished video in the UI after Generate was clicked.
2. **Runtime side:** Strict completion gate never saw a completed, scoped artifact card for Clip 1:
   - `clip_1_completion_verified: false`
   - `generation_in_progress` persisted through timeout
   - `stop_cancel_visible: true` at end
   - Artifact tracker returned **zero** cards at timeout
3. **Pipeline gate:** Clip 2 only begins after Clip 1 **download + settle** (steps 018–019), then Use Frame (020). None of those ran.

So the run **correctly stopped before Clip 2**, but the blocking failure was **Clip 1 completion detection**, not Clip 2 Use Frame.

---

## Stale failure diagnostics file (do not confuse with this run)

`runway_phase_i_last_failure_diagnostics.json` describes a **different** scenario:

| Field | Stale file | This live run |
|-------|------------|---------------|
| Timestamp | 2026-06-04 20:54:33 | 2026-06-07 15:44–16:33 |
| Failed step | `021_verify_use_frame_handoff_clip_2` | `017_wait_until_completion_signal_clip_1` |
| Error | `"test"` | strict completion timeout |
| Handoff result | `invalid_card_only` | N/A (never reached) |

That file is **not** evidence for the 2026-06-07 perfume Content Brain run.

---

## Evidence files

| File | Relevance |
|------|-----------|
| `runway_phase_i_3clip_last_report.json` | Full report, action log, errors |
| `runway_phase_i_completion_gate_diagnostics.json` | **Timeout state for Clip 1 gate** |
| `PHASE_RUNWAY_STARTER_TO_VIDEO_I_3CLIP_LIVE_REPORT.md` | Human-readable run summary |
| `runway_live_smoke_artifacts/phase_i_live_strict_completion_pending_clip_1_*.png` | 27 poll screenshots during step 017 |
| `runway_live_smoke_artifacts/phase_i_live_strict_completion_timeout_clip_1_1780842759.png` | Final timeout screenshot |

---

## Conclusion

| Question | Answer |
|----------|--------|
| Exact step reached | Through `016_video_generate_manual_required_clip_1` (generate clicked); entered `017_wait_until_completion_signal_clip_1` |
| Exact step failed | **`017_wait_until_completion_signal_clip_1`** |
| Clip 2 reached? | **No** — blocked by Clip 1 strict completion timeout |
| Failure class | Completion detection / artifact tracking — not Use Frame, not Clip 2 prompt, not Clip 2 generate gate |
| `latest_video_card` fingerprint at failure | `488\|-247\|608\|439\|video\|…` (stale/prior-run text; gate had empty assignment) |
| Use Frame (Clip 2) | Never attempted |
| Clip 2 prompt | Planned only — never filled |

**Diagnostic-only. No fixes applied.**
