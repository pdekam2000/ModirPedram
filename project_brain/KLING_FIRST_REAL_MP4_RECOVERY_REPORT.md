# Kling First Real MP4 Recovery — Report

**Phase:** `KLING-FIRST-REAL-MP4-RECOVERY`  
**Status:** SUCCESS — first real Kling MP4 recovered  
**Date:** 2026-06-17  
**Run ID:** `kling_ms_20260617T035534_f392af70`

---

## 1. Problem

Kling Native Audio generation completed in Runway UI (Generate clicked, credits spent, render visible), but automation failed at download/save. No real MP4 existed under the canonical clip folder — only mock validation placeholders (~32 bytes–1 KB).

---

## 2. Root Cause

The Kling download path relied on global UI `expect_download()` clicks. Runway exposes the finished Kling output as a **scoped artifact card video** with a direct **CloudFront MP4 URL**, not a reliable browser download event.

The working source was recovered via existing **Runway Phase I CDP download** (`PhaseIArtifactTracker` + `RunwayPhaseICdpDownloader`), strategy `cdp_fetch`.

---

## 3. Fix (Download Only)

### Reused Runway browser logic

Enhanced `content_brain/execution/kling_multishot_live_engine.py`:

| Strategy | Source |
|----------|--------|
| `runway_cdp:cdp_fetch` | `RunwayPhaseICdpDownloader` + artifact card tracker (**winning strategy**) |
| UI download button | Existing Playwright `expect_download` fallback |
| Blob / HTTP fetch | In-page fetch from `<video src>` |
| Performance resource URLs | Browser performance entries |
| `page.context.request.get` | Authenticated HTTP fallback |

Added:

- `verify_recovered_mp4()` — size > 1 MB, duration > 1s, ffprobe pass, not placeholder
- `MIN_REAL_MP4_BYTES = 1_048_576`
- Recovery rejects placeholder/small files

### Recovery CLI

```bash
python tools/kling_recover_first_real_mp4.py \
  --run-id kling_ms_20260617T035534_f392af70 \
  --clip-index 1
```

No Generate click. No new credits.

---

## 4. Recovery Result

| Check | Value |
|-------|-------|
| Strategy | `runway_cdp:cdp_fetch` |
| Source URL | CloudFront Kling 3.0 Pro MP4 |
| Clip path | `outputs/kling_multishot_live/kling_ms_20260617T035534_f392af70/clips/c1/video.mp4` |
| Root path | `outputs/kling_multishot_live/kling_ms_20260617T035534_f392af70/video.mp4` |
| Size | **31,351,902 bytes (~29.9 MB)** |
| Duration | **15.04 seconds** |
| ffprobe | PASS |
| Audio | Native audio track detected |
| Generate clicked | false |
| Credits spent | false |
| output_ready | true |

---

## 5. Files Modified / Created

| File | Change |
|------|--------|
| `content_brain/execution/kling_multishot_live_engine.py` | Runway CDP download integration + MP4 verification |
| `content_brain/execution/kling_product_run.py` | Recovery verifies real MP4 before marking success |
| `tools/kling_recover_first_real_mp4.py` | Recovery CLI for this phase |
| `project_brain/validate_kling_first_real_mp4_recovery.py` | Validation suite |
| `project_brain/KLING_FIRST_REAL_MP4_RECOVERY_REPORT.md` | This report |

---

## 6. Validation

```bash
python project_brain/validate_kling_first_real_mp4_recovery.py
python project_brain/validate_kling_download_recovery_fix.py
```

**All checks passed**

| # | Test | Result |
|---|------|--------|
| 1 | MP4 exists | PASS |
| 2 | Size > 1 MB | PASS (~30 MB) |
| 3 | Duration detected | PASS (15.04s) |
| 4 | ffprobe passes | PASS |
| 5 | Not placeholder | PASS |
| 6 | Recovery does not Generate | PASS |
| 7 | Recovery spends no credits | PASS |
| 8 | Recovery updates metadata | PASS |
| 9 | Recovery updates download report | PASS |
| 10 | output_ready=true | PASS |

---

## 7. Operator Verification

Open in Windows Media Player:

```text
outputs/kling_multishot_live/kling_ms_20260617T035534_f392af70/clips/c1/video.mp4
```

Expected: ~15s Kling Native Audio video with character voices and environment audio.

---

## 8. Next Phase (Blocked Until This — Now Unblocked)

Proceed to:

1. Kling Continuity Chain
2. Clip 2 → Clip 3 multi-clip production
3. Wire Runway CDP download into normal post-generate path (not only recovery)

Do **not** start Continuity Chain until operator confirms playback in Media Player.
