# Phase I — Artifact Tracking + CDP Download Strategy

**Date:** 2026-06-04  
**Status:** Implemented in live runtime path; validated (structural + simulate rehearsal)

This report covers **artifact card tracking + CDP-preferred download only**. (Last-frame Use Frame is a separate phase — see `PHASE_I_GENERIC_LAST_FRAME_USE_FRAME_FIX_REPORT.md`.)

---

## Confirmation checklist

| Question | Answer |
|----------|--------|
| Implemented in **live runtime**, not only validator? | **Yes** — wired through `RunwayLiveSmokeRunner` → `RunwayContinuitySemiAutoEngine` → `MappedRunwayUINavigator` on every Phase I run (CDP and simulate). |
| Clip 1 / 2 / 3 cards assigned **separately**? | **Yes** — roles `starter_image_card`, `clip_1_video_card`, `clip_2_video_card`, `clip_3_video_card` via diff-after-snapshot assignment. |
| Download + Use Frame **scoped** to tracked cards? | **Yes** — `download_assigned_clip_video`, `click_use_frame_for_next_clip` / `click_label_on_assigned_card` (Use Frame also goes through last-frame prepare for N>1). |
| Starter image **excluded** from clip download/use-frame? | **Yes** — `mark_consumed(ROLE_STARTER_IMAGE)` after Use-to-Video; `ensure_starter_not_used_for_clip_ops()` raises on fingerprint collision. |
| CDP/network download **audited**? | **Yes** — see [CDP audit](#cdp-network-download-audit) below. |
| CDP download **implemented** or UI-only? | **Both** — CDP fetch is implemented first; UI fallback remains when no safe http(s) URL. |
| `validate_phase_i_artifact_tracking_and_cdp_download.py` | **All checks PASS** (run 2026-06-04) — see [Validation results](#validation-results). |

---

## Problem

All generated artifacts (starter image + clip 1/2/3 videos) stay visible in the Runway session. Global Download / Use Frame clicks can hit the wrong card. Deleting the starter image is not the fix — the runtime must know which card belongs to which step.

Browser UI download is fragile; prefer CDP/network download when a safe media URL exists.

---

## Part A — Artifact card tracking (live path)

**Module:** `content_brain/execution/runway_phase_i_artifact_tracker.py`

| Role | When assigned | Notes |
|------|----------------|-------|
| `starter_image_card` | Registered from latest image selection | **Marked consumed** after Use-to-Video (not deleted) |
| `clip_1_video_card` | After `wait_until_completion_signal_clip_1` | New video card vs pre-generate snapshot |
| `clip_2_video_card` | After clip 2 completion wait | Same diff logic |
| `clip_3_video_card` | After clip 3 completion wait | Same diff logic |

**Live wiring:**

1. `runway_live_smoke_test.py` — `configure_phase_i_artifact_tracking(project_id, session_id, cdp_preferred)` when CDP page is connected (line ~819).
2. `runway_continuity_semi_auto.py` — `snapshot_before_generation` before each video generate; `assign_clip_video_artifact(clip_index)` after strict completion wait.
3. `runway_ui_navigator.py` — `_register_starter_image_assignment` + `mark_consumed(ROLE_STARTER_IMAGE)` on Use-to-Video paths.

**Scoped actions:**

- **Download clip N** → `download_assigned_clip_video(N)` uses `clip_N_video_card` fingerprint + `extract_media_urls_for_role`.
- **Use Frame for clip N** (N>1) → prior clip card via `click_use_frame_for_next_clip` / last-frame prepare (separate phase).

**Guard:** `ensure_starter_not_used_for_clip_ops(clip_index)` — starter fingerprint cannot be used for clip download or use-frame.

**Diagnostics:** `project_brain/runway_phase_i_artifact_card_diagnostics.json`

**Fix applied:** Removed `assign_new_card` fallback that coerced `cardType` to match `prefer_type` (could assign starter fingerprint to a clip video role).

---

## Part B — CDP / network download

**Module:** `content_brain/execution/runway_phase_i_cdp_download.py`

**Config (set on live runner):**

- `download_strategy = "cdp_preferred"`
- `fallback_to_ui_download = true`

**Live wiring:** `runway_continuity_semi_auto.py` download steps call `nav.download_assigned_clip_video(clip_index, …)` — not bare global `click_control("download_mp4_button")` only.

### CDP / network download audit

Sources checked per assigned card (page `evaluate`):

| Source | Used in code |
|--------|----------------|
| `video.currentSrc` / `video.src` | Yes — card scan + `_media_urls_for_card_eval_script` |
| `<img>` src | Yes — image cards only |
| `<a download>` / `.mp4` hrefs | Yes — collected in card scan |
| `blob:` URLs | **Skipped** — `_is_downloadable_url` rejects blob |
| Network response capture (CDP Network domain) | **Not** — no passive HAR-style listener; URLs come from DOM |
| Download button `href` | Indirect — via card button scan, not global control map |

**Download order (live, non-simulate):**

1. **`cdp_fetch`** — `page.evaluate` async `fetch(url)` → base64 → write `downloads/runway/runway_clip_{N}_{session}_{timestamp}.mp4`
2. **`cdp_fetch`** (retry) — `requests.get` for same http(s) URL if page fetch fails
3. **`ui_fallback`** — scoped Download click on assigned card (`click_label_on_assigned_card`), then `RunwayPhaseIDownloadTracker.verify_clip_download`
4. **`dir_verify`** — directory poll only if UI path did not confirm file

**Simulate path:** writes placeholder bytes via CDP URL branch (`strategy: cdp_url`); UI fallback tested when `media_urls` empty.

**Not implemented:** Chrome CDP `Browser.downloadBehavior`, signed-URL interception, or blob-to-file mapping without a fetchable http(s) URL. In those cases expect **`ui_fallback`** with `fallback_reason: no_safe_direct_url` in diagnostics.

**Diagnostics:** `project_brain/runway_phase_i_download_diagnostics.json` — detected URLs, chosen strategy, fallback reason, file verification.

---

## Integration map (live runtime)

```
Execution Center / API
  run_live_smoke_test() / RunwayLiveSmokeRunner.run()
    configure_phase_i_artifact_tracking()
    RunwayContinuitySemiAutoEngine.advance()
      snapshot_before_generation (per clip video generate)
      wait_for_strict_clip_completion → assign_clip_video_artifact
      download_assigned_clip_video → RunwayPhaseICdpDownloader.download_clip()
      prepare_last_frame_use_frame_for_clip → scoped Use Frame (separate phase)
```

| File | Responsibility |
|------|----------------|
| `runway_phase_i_artifact_tracker.py` | Card fingerprints, roles, scoped clicks, consumed starter |
| `runway_phase_i_cdp_download.py` | CDP fetch + UI fallback + file verify |
| `runway_ui_navigator.py` | Tracker/CDP bridge, assign, download, use-frame scoped click |
| `runway_continuity_semi_auto.py` | Step hooks for snapshot, assign, download |
| `runway_live_smoke_test.py` | Live CDP connect, configure tracking, report fields |
| `ui/api/runway_live_smoke_service.py` | Same runner for Runtime Studio UI |

---

## Report fields (`runway_phase_i_3clip_last_report.json`)

- `artifact_card_assignments`
- `clip_1_download_strategy`, `clip_2_download_strategy`, `clip_3_download_strategy`
- `clip_1_download_scoped_to_card`, `clip_2_download_scoped_to_card`, `clip_3_download_scoped_to_card`
- `downloaded_file_paths`, `total_downloads_completed`, `download_dir`, `download_records`

After a live run, expect `clip_N_download_strategy` of `cdp_fetch` when Runway exposes a fetchable URL on the assigned card; otherwise `ui_fallback`.

---

## Validation results

Command:

```bash
python project_brain/validate_phase_i_artifact_tracking_and_cdp_download.py
```

**Last run: all checks PASS**

| Check | Result |
|-------|--------|
| Modules present (`PhaseIArtifactTracker`, `RunwayPhaseICdpDownloader`) | PASS |
| `download_assigned_clip_video`, scoped use-frame, assign clip | PASS |
| Starter consumed, not deleted; not reused for clip 1 ops | PASS |
| CDP sim download `cdp_url`, scoped | PASS |
| UI fallback when no URL (`ui_fallback`) | PASS |
| Artifact + download diagnostics files | PASS |
| 7 approval gates (3-clip) | PASS |
| Simulate 3-clip rehearsal `completed` | PASS |
| Report strategy / scoped / paths / total_downloads | PASS |
| StoryBrief / Prompt Builder / Provider Router untouched | PASS |

Related validators (not replaced by this script):

- `validate_phase_i_use_frame_handoff_verification.py`
- `validate_phase_i_false_fail_while_generating.py`
- `validate_runway_phase_i_3clip_live_continuity.py`
- `validate_phase_i5_download_and_progression.py`

---

## Operator verification (live CDP)

After **Start 3-Clip Live (CDP)**:

1. `project_brain/runway_phase_i_3clip_last_report.json` — per-clip `download_strategy`, `download_scoped_to_card`, `artifact_card_assignments`
2. `project_brain/runway_phase_i_artifact_card_diagnostics.json` — snapshots and role assignments
3. `project_brain/runway_phase_i_download_diagnostics.json` — URLs tried, `chosen_download_strategy`, `fallback_reason`

If downloads always show `ui_fallback`, inspect `detected_media_urls` — Runway may only expose `blob:` or UI download without a stable http(s) URL in DOM.

---

## Unchanged (constraints)

- StoryBrief Builder, Prompt Builder content, Provider Router
- **7** approval gates for 3-clip Phase I
- Voice / Subtitle / Assembly
