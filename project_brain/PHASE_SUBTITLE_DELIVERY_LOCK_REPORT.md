# PHASE SUBTITLE-DELIVERY-LOCK Report

- **Run ID:** `cb_e2e_20260613_162423_dcde7693`
- **Topic:** Dog Training like pro
- **Completed:** 2026-06-13T17:26:53.362958+00:00

## Root cause

The delivered `FINAL_BRANDED_VIDEO.mp4` shipped without readable burned subtitles because branding marked the subtitle burn as failed and continued on the pre-subtitle video. CTA overlay was applied to the non-subtitled source, so the final MP4 failed the MP4-only subtitle bbox audit (`white_ratio` far below threshold).

## Drawtext renderer fixes (`subtitle_format_engine_v6` / `subtitle_burn_engine_v8`)

- Font size scaled to 5.2% of video height (min 52, preferred 64).
- High-contrast outline: `borderw=6`, `bordercolor=black@1.0`.
- Readable backing box: `box=1:boxcolor=black@0.55:boxborderw=12`.
- Lower-third safe zone preserved via `compute_lower_third_margin_v()`.
- Burn gate now verifies output frames with `measure_subtitle_text_bbox()` (height ≥ 18).

## Before (delivered MP4 frame audit)

- Video: `C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260613_170300_423_dcde7693\publish\FINAL_BRANDED_VIDEO.mp4`

| Sample (s) | Visible | White ratio | BBox W×H |
|---|---:|---:|---:|
| 1.0 | False | 0.0 | 0×0 |
| 3.0 | False | 5e-06 | 1×1 |
| 5.0 | False | 0.000182 | 101×63 |
| 8.0 | False | 0.0 | 0×0 |

- Delivery audit: **FAIL** — failures: `['subtitles']`

## After (`FINAL_BRANDED_VIDEO_subtitle_fixed.mp4`)

- Video: `C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260613_170300_423_dcde7693\publish\FINAL_BRANDED_VIDEO_subtitle_fixed.mp4`

| Sample (s) | Visible | White ratio | BBox W×H |
|---|---:|---:|---:|
| 1.0 | True | 0.039665 | 720×61 |
| 3.0 | True | 0.03967 | 720×61 |
| 5.0 | True | 0.040523 | 720×125 |
| 8.0 | True | 0.039347 | 720×49 |

- Subtitle burn: `COMPLETED` — visible enough: `True`
- Delivery audit: **PASS** — checks: `{'subtitles': True, 'music': True, 'ambience': True, 'dialogue': True, 'voice_separation': True, 'story_quality': True, 'no_silent_gaps': True}`
- Failures: `[]`
- Approved: **True**

## Output

`C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260613_170300_423_dcde7693\publish\FINAL_BRANDED_VIDEO_subtitle_fixed.mp4`
