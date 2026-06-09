# Phase I — Video Playback Controls Mapping (Last-Frame Seek)

**Date:** 2026-06-04  
**Status:** Implemented in live runtime; validation PASS

## Purpose

Before **Use Frame** for clip N > 1, the runtime must seek the **previous clip’s** artifact-card `<video>` to the last safe frame. This report confirms how playback is controlled and that **Stop/Cancel generation** is not confused with play/pause.

---

## Confirmation checklist

| Question | Answer |
|----------|--------|
| HTML `<video>` seek works? | **Yes** — primary path sets `video.currentTime` to `duration - 0.7s` (or ~92% of duration). |
| Timeline fallback works? | **Yes** — if `currentTime` seek fails, in-card `input[type=range]` / slider at ~93%, or `video.currentTime = duration * timelinePercent`. |
| Play/pause vs stop generation confused? | **No** — seek uses **`HTMLVideoElement.pause()` API only**; does not click Play/Pause/Stop/Cancel buttons. Generation abort labels (`Stop generation`, `Cancel render`, …) are never clicked during seek. |
| Connected to live runtime? | **Yes** — `runway_continuity_semi_auto.py` → `nav.prepare_last_frame_use_frame_for_clip()` → CDP `page.evaluate(last_frame_seek_eval_script)`. |
| Validation PASS? | **Yes** — `python project_brain/validate_phase_i_video_playback_controls.py` |

---

## Control mapping

### Safe (used for last-frame seek)

| Method | Scope | Notes |
|--------|--------|------|
| `HTMLVideoElement.currentTime` | `<video>` inside assigned artifact card | Primary seek |
| `HTMLVideoElement.pause()` | Same `<video>` | Pause after seek (API, not button) |
| In-card range / slider | `targetCard.querySelector('input[type=range], [role=slider], …')` | Fallback scrub ~90–95% |

### Never clicked during seek

| Control type | Examples | Detection |
|--------------|----------|-----------|
| Generation abort | Stop generation, Cancel render, Abort queue | `is_generation_abort_button_label()` |
| Composer Generate | Global generate (separate step) | Not invoked in seek script |
| Global Download / Use Frame | Only after seek completes | Separate scoped click |

### In-card playback buttons (informational only)

Play / Pause / Mute labels inside the card are **audited** (`audit_card_playback_controls`) but **not clicked** — seek uses video element APIs instead.

---

## Live runtime flow

```
use_frame_for_clip_N  (N > 1)
  prepare_last_frame_use_frame_for_clip(N)
    evaluate_strict_clip_completion(N-1)
    audit_card_playback_controls(previous card)  → diagnostics
    _seek_video_in_card (currentTime)
      └─ on failure → timeline_percent fallback
    write_playback_controls_diagnostics
    click_use_frame_for_next_clip(N)  (scoped to clip N-1 card)
```

**Modules:**

- `content_brain/execution/runway_phase_i_last_frame_use_frame.py` — seek eval + prepare
- `content_brain/execution/runway_phase_i_video_playback_controls.py` — mapping, audit, diagnostics
- `content_brain/execution/runway_ui_navigator.py` — wrapper
- `content_brain/execution/runway_continuity_semi_auto.py` — step hook

**Diagnostics:** `project_brain/runway_phase_i_video_playback_controls_diagnostics.json`

---

## Seek result fields

Per last-frame prepare (`LastFrameUseFrameResult` / `use_frame_last_frame_by_clip`):

- `playback_seek_method` — `html_video_currentTime` | `timeline_range_in_card` | `timeline_video_currentTime_percent` | `simulate`
- `generation_controls_avoided` — `true` when seek script reports `generationControlClickAttempted: false`
- `seek_time_used`, `seek_strategy`, `previous_clip_seeked_to_last_frame`

---

## Validation

```bash
python project_brain/validate_phase_i_video_playback_controls.py
```

**Checks:** seek script contains `currentTime` + `pause`; timeline fallback; no generation button clicks in script; generation vs playback label classifier; live semi-auto/navigator wiring; simulate 3-clip rehearsal; report fields.

---

## Operator note (live CDP)

After a run, open `runway_phase_i_video_playback_controls_diagnostics.json` for the clip being chained:

- `audit.in_card_playback_buttons` — Play/Pause inside card (not clicked)
- `audit.in_card_generation_abort_buttons` — should be empty inside card; global list is informational
- `seek_result.seekMethod` — should be `html_video_currentTime` when metadata loaded
- `seek_result.afterTime` — should be near end (e.g. ~9s for 10s clip)

If `seekMethod` is timeline fallback every time, Runway may not expose `video.duration` until playback — still safe (no Stop generation click).
