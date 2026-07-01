# KLING REAL MP4 DOWNLOAD EXTRACTOR REPORT

Generated: 2026-06-20

## Problem

Run `kling_ft_20260620T154336_8a10548a` generated Clip 1 successfully but download/recovery saved a placeholder (`studio-empty-state.webm`) instead of a real MP4. The old `_download_output` path returned any file > 4KB without requiring ffprobe-valid MP4.

## Solution

New module: `content_brain/execution/kling_real_mp4_download_extractor.py`

### Behavior

1. **URL filtering** — rejects `empty-state`, `studio-empty`, `/app/empty`, and other placeholder URLs before fetch.
2. **Strict validation** — only registers output when:
   - file exists
   - size > 1MB
   - MP4 container (`ftyp` magic)
   - ffprobe valid
   - duration >= 5s
3. **Quarantine** — invalid downloads moved to `clips/cN/quarantine/` with `.inspect.json` (type, size, header bytes).
4. **Extraction methods** (no Generate, no credits):
   - `artifact_card_cdp_urls` — scoped card URLs, sorted by Kling/cloudfront/.mp4 preference
   - `scoped_card_browser_download` — Apps menu + Download MP4 on assigned video card + download dir verify
   - `page_video_sources` — filtered video/src + performance network URLs
   - `global_ui_download` — last-resort UI download button

### Wiring

- `_download_output()` in `kling_multishot_live_engine.py` delegates to `extract_real_kling_mp4()`.
- `runway_phase_i_cdp_download.py` skips placeholder URLs in CDP fetch loop.
- `_download_via_runway_phase_i()` no longer returns non-real MP4 on size alone.
- `recover_kling_frame_output()` uses extractor; writes `clip_N.mp4` + `video.mp4` copy.

## Recovery command

```bash
python project_brain/recover_kling_real_mp4_from_current_browser.py --run-id kling_ft_20260620T154336_8a10548a
```

Requirements:
- Chrome visible on CDP `:9222` with generated output on screen
- Does **not** click Generate or spend credits

Output paths:
- `outputs/kling_frame_to_video/<run_id>/clips/c1/clip_1.mp4`
- `outputs/kling_frame_to_video/<run_id>/clips/c1/video.mp4` (copy)

## Live recovery result (`kling_ft_20260620T154336_8a10548a`)

| Field | Result |
|-------|--------|
| **recovery ok** | yes |
| **method** | `artifact_card_cdp_urls:verify_0` |
| **size** | 31,906,808 bytes (~30.4 MB) |
| **duration** | 15.04s |
| **ffprobe** | pass |
| **container** | MP4 (`ftypisom`) |
| **credits spent** | no |
| **quarantined** | none |

Extract report: `outputs/kling_frame_to_video/kling_ft_20260620T154336_8a10548a/clips/c1/mp4_extract_report.json`

## Validation

```bash
python project_brain/validate_kling_real_mp4_download_extractor.py
```

All checks passed (placeholder rejection, quarantine, real MP4 acceptance, no Generate in recovery path, attempted methods in report).

## Files

| File | Role |
|------|------|
| `content_brain/execution/kling_real_mp4_download_extractor.py` | Extractor + quarantine + verify |
| `content_brain/execution/kling_multishot_live_engine.py` | `_download_output` → extractor |
| `content_brain/execution/kling_frame_to_video_live_engine.py` | stricter verify + recovery |
| `content_brain/execution/runway_phase_i_cdp_download.py` | placeholder URL skip |
| `project_brain/recover_kling_real_mp4_from_current_browser.py` | Recovery CLI |
| `project_brain/validate_kling_real_mp4_download_extractor.py` | Validation |
