# Phase RUNWAY-STARTER-TO-VIDEO-H — Live Operator-Approved Smoke Test Report

**Phase:** `runway_starter_to_video_h_v1`
**Project:** `phase_i_manual_validate`
**Mode:** Simulate rehearsal (no CDP)
**Started:** 2026-06-08 21:37:22
**Finished:** 2026-06-08 21:37:28
**Result:** PASS

## Scope (Phase H)

- 1 starter image + 1 video clip only
- `simulate=False` for real live smoke (CDP Chrome required)
- Generate / Download require explicit operator `APPROVE`
- Manual image-ready hold requires operator `READY`
- No multi-clip loop; no autonomous Generate/Download

### Expected flow

1. Prompt Builder → plan (`clip_count=1`)
2. Semi-auto prep (prompt, 9:16, 2K)
3. Pause → `image_generate_button` → operator APPROVE
4. Manual hold → image ready → operator READY
5. App menu → Use to Video
6. Fill video prompt + duration
7. Pause → `generate_button` → operator APPROVE
8. Wait completion (≤ 25 min)
9. Pause → `download_mp4_button` → operator APPROVE
10. `remove_image` → finish

---

## Browser & Map

| Check | Value |
|-------|-------|
| Browser connected | No |
| Probe message | (none) |
| Probe passed | (unknown) |
| Probe reject code | (none) |
| Page URL (last) | (none) |
| Controls resolved | 25/24 |
| Controls missing | (none) |
| Dry-run ok | Yes |
| Steps in plan | 19 |
| Clip count | 1 (single-clip smoke) |

## Operator Approvals

| Control | Step | Label | Granted | Operator | Time |
|---------|------|-------|---------|----------|------|
| `image_generate_button` | `008_image_generate_manual_required` | Image Generate (spends credits) | Yes | operator | 2026-06-08 21:37:26 |
| `generate_button` | `016_video_generate_manual_required_clip_1` | Video Generate (spends credits) | Yes | operator | 2026-06-08 21:37:28 |
| `download_mp4_button` | `018_final_download_clip_1` | Download MP4 | Yes | operator | 2026-06-08 21:37:28 |

## Manual Holds

_None._

## Image Settings Diagnostics

| Check | Value |
|-------|-------|
| detected_aspect_ratio | 9:16 |
| detected_image_count | 1 |
| detected_image_quality | 2K |
| settings_verified | Yes |
| image_prompt_cleared | Yes |
| prompt_text_before_clear | 0 chars |
| prompt_text_after_clear | 0 chars |

## Latest Image Card Diagnostics

| Check | Value |
|-------|-------|
| latest_image_card_found | Yes |
| latest_image_card_index | 0 |
| selected_image_card_fingerprint | 20|480|260|400|cinematic realistic vertical 9:16 hero starter frame. static hold composition for reference image generation. subject: w |
| selected_image_card_index | 0 |
| card_prompt_text | cinematic realistic vertical 9:16 hero starter frame. Static hold composition for reference image generation. Subject: W |
| card_bounding_box | {'x': 20.0, 'y': 480.0, 'width': 260.0, 'height': 400.0} |
| video_transition_verified | Yes |
| current_url_after_transition | https://app.runwayml.com/ai-tools/generate?mode=tools&tool=video |
| used_image_card_removed | No |
| used_image_card_marked_consumed | Yes |
| video_generation_started | Yes |
| browser_state | (none) |
| detected_video_aspect_ratio | 9:16 |
| detected_video_duration | 10s |
| video_settings_verified | Yes |

### Toolbar Chip Screenshots

| When | Detected chips |
|------|----------------|
| read #1 | count=; aspect=; quality=; duration= |
| read #2 | count=; aspect=9:16; quality=; duration= |
| read #3 | count=; aspect=9:16; quality=; duration= |
| read #4 | count=1; aspect=9:16; quality=; duration= |
| read #5 | count=1; aspect=9:16; quality=; duration= |
| read #6 | count=1; aspect=9:16; quality=2K; duration= |
| read #7 | count=1; aspect=9:16; quality=2K; duration= |
| read #8 | count=1; aspect=9:16; quality=2K; duration= |
| read #9 | count=1; aspect=9:16; quality=2K; duration= |
| read #10 | count=1; aspect=9:16; quality=2K; duration= |
| read #11 | count=1; aspect=9:16; quality=2K; duration= |
| read #12 | count=1; aspect=9:16; quality=2K; duration= |
| read #13 | count=1; aspect=9:16; quality=2K; duration= |
| read #14 | count=1; aspect=9:16; quality=2K; duration= |
| read #15 | count=1; aspect=9:16; quality=2K; duration= |
| read #16 | count=1; aspect=9:16; quality=2K; duration= |
| read #17 | count=1; aspect=9:16; quality=2K; duration= |
| read #18 | count=1; aspect=9:16; quality=2K; duration=10s |
| read #19 | count=1; aspect=9:16; quality=2K; duration=10s |
| read #20 | count=1; aspect=9:16; quality=2K; duration=10s |
| read #21 | count=1; aspect=9:16; quality=2K; duration=10s |
| read #22 | count=1; aspect=9:16; quality=2K; duration=10s |

## Execution Results

| Stage | Result |
|-------|--------|
| Image generation | generate_clicked_with_approval |
| Video completion detected | Yes |
| Completion signals | strict_clip_complete, download_in_card |
| Download attempted | Yes |
| Download confirmed | Yes |
| remove_image executed | Yes |
| Final session status | `completed` |

## Safety Stops

**Stopped reason:** (completed normally)

### Warnings

- simulate=True: browser connection skipped
- story progression audit flagged weak discovery/escalation/payoff separation

## Safety Confirmation

| Gate | Value |
|------|-------|
| simulate | True |
| Autonomous Generate | Blocked without APPROVE |
| Autonomous Download | Blocked without APPROVE |
| Max completion wait | 25 minutes |

## Run Command

**Live CDP smoke (operator at keyboard):**

```bash
# 1. Open Chrome with CDP (app Open Browser or launcher)
# 2. Log into Runway
python project_brain/run_runway_live_smoke_test.py --story "Your story idea..."
```

**Structural rehearsal (no browser):**

```bash
python project_brain/run_runway_live_smoke_test.py --simulate --story "..."
python project_brain/validate_runway_live_smoke_test.py
```

**Safety stops:** selector fail · unexpected page · missing approval · completion > 25 min
