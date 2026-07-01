# Phase RUNWAY-STARTER-TO-VIDEO-H — Live Operator-Approved Smoke Test Report

**Phase:** `runway_starter_to_video_h_v1`
**Project:** `acf_test_01_20260619T194627_3e1aa9d2`
**Mode:** Live CDP smoke
**Started:** 2026-06-19 21:46:28
**Finished:** 2026-06-19 22:22:10
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
| Browser connected | Yes |
| Probe message | browser probe failed |
| Probe passed | True |
| Probe reject code | (none) |
| Page URL (last) | https://app.runwayml.com/video-tools/teams/kamangarpedram/ai-tools/generate?mode=tools&tool=video&sessionId=5920152d-ba9d-4d74-81c0-534f4b43486c |
| Controls resolved | 25/24 |
| Controls missing | (none) |
| Dry-run ok | Yes |
| Steps in plan | 19 |
| Clip count | 1 (single-clip smoke) |

## Operator Approvals

_No approval events recorded._

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
| selected_image_card_fingerprint | 621|164|476|853| |
| selected_image_card_index | 0 |
| card_prompt_text | (none) |
| card_bounding_box | {'x': 621.0703125, 'y': 164.0, 'width': 475.859375, 'height': 852.578125} |
| video_transition_verified | Yes |
| current_url_after_transition | https://app.runwayml.com/video-tools/teams/kamangarpedram/ai-tools/generate?mode=tools&tool=video&sessionId=5920152d-ba9d-4d74-81c0-534f4b43486c |
| used_image_card_removed | No |
| used_image_card_marked_consumed | Yes |
| video_generation_started | Yes |
| browser_state | (none) |
| detected_video_aspect_ratio | 9:16 |
| detected_video_duration | 10s |
| video_settings_verified | Yes |

### Latest Image Card Screenshots

- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_latest_image_before_scroll_1781899081.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_latest_image_after_scroll_1781899084.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_latest_image_app_menu_open_1781899087.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_latest_image_use_to_video_before_image_use_to_vi_1781899091.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_latest_image_use_to_video_after_image_use_to_vid_1781899094.png`

### Toolbar Chip Screenshots

| When | Detected chips |
|------|----------------|
| read #1 | count=4; aspect=9:16; quality=1K; duration= |
| read #2 | count=4; aspect=9:16; quality=1K; duration= |
| read #3 | count=4; aspect=9:16; quality=1K; duration= |
| read #4 | count=4; aspect=9:16; quality=1K; duration= |
| read #5 | count=1; aspect=9:16; quality=1K; duration= |
| read #6 | count=1; aspect=9:16; quality=1K; duration= |
| read #7 | count=1; aspect=9:16; quality=1K; duration= |
| read #8 | count=1; aspect=9:16; quality=1K; duration= |
| read #9 | count=1; aspect=9:16; quality=1K; duration= |
| read #10 | count=1; aspect=9:16; quality=2K; duration= |
| read #11 | count=1; aspect=9:16; quality=2K; duration= |
| read #12 | count=1; aspect=9:16; quality=2K; duration= |
| read #13 | count=1; aspect=9:16; quality=2K; duration= |
| read #14 | count=1; aspect=9:16; quality=2K; duration= |
| read #15 | count=1; aspect=9:16; quality=2K; duration= |
| read #16 | count=1; aspect=9:16; quality=2K; duration= |
| read #17 | count=1; aspect=9:16; quality=2K; duration= |
| read #18 | count=1; aspect=9:16; quality=2K; duration= |
| read #19 | count=1; aspect=9:16; quality=2K; duration= |
| read #20 | count=1; aspect=9:16; quality=2K; duration= |
| read #21 | count=1; aspect=9:16; quality=2K; duration= |
| read #22 | count=; aspect=9:16; quality=; duration=5s |
| read #23 | count=; aspect=9:16; quality=; duration=5s |
| read #24 | count=; aspect=9:16; quality=; duration=5s |
| read #25 | count=; aspect=9:16; quality=; duration=5s |
| read #26 | count=; aspect=9:16; quality=; duration=5s |
| read #27 | count=; aspect=9:16; quality=; duration=5s |
| read #28 | count=; aspect=9:16; quality=; duration=5s |
| read #29 | count=; aspect=9:16; quality=; duration=5s |
| read #30 | count=; aspect=9:16; quality=; duration=10s |
| read #31 | count=; aspect=9:16; quality=; duration=10s |
| read #32 | count=; aspect=9:16; quality=; duration=10s |
| read #33 | count=; aspect=9:16; quality=; duration=10s |
| read #34 | count=; aspect=9:16; quality=; duration=10s |
| read #35 | count=; aspect=9:16; quality=; duration=10s |
| read #36 | count=; aspect=9:16; quality=; duration=10s |
| read #37 | count=; aspect=9:16; quality=; duration=10s |
| read #38 | count=; aspect=9:16; quality=; duration=10s |
| read #39 | count=; aspect=9:16; quality=; duration=10s |
| read #40 | count=; aspect=9:16; quality=; duration=10s |
| read #41 | count=; aspect=9:16; quality=; duration=10s |
| read #42 | count=; aspect=9:16; quality=; duration=10s |
| read #43 | count=; aspect=9:16; quality=; duration=10s |
| read #44 | count=; aspect=9:16; quality=; duration=10s |
| read #45 | count=; aspect=9:16; quality=; duration=10s |
| read #46 | count=; aspect=9:16; quality=; duration=10s |
| read #47 | count=; aspect=9:16; quality=; duration=10s |
| read #48 | count=; aspect=9:16; quality=; duration=10s |
| read #49 | count=; aspect=9:16; quality=; duration=10s |
| read #50 | count=; aspect=9:16; quality=; duration=10s |
| read #51 | count=; aspect=9:16; quality=; duration=10s |
| read #52 | count=; aspect=9:16; quality=; duration=10s |
| read #53 | count=; aspect=9:16; quality=; duration=10s |
| read #54 | count=; aspect=9:16; quality=; duration=10s |
| read #55 | count=; aspect=9:16; quality=; duration=10s |
| read #56 | count=; aspect=9:16; quality=; duration=10s |
| read #57 | count=; aspect=9:16; quality=; duration=10s |
| read #58 | count=; aspect=9:16; quality=; duration=10s |
| read #59 | count=; aspect=9:16; quality=; duration=10s |

Captured chip diagnostic screenshots:

- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_chip_detect_before_image_aspect_ratio_menu_1781898393.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_chip_detect_before_image_count_menu_1781898397.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_chip_detect_before_image_quality_menu_1781898525.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_chip_detect_before_image_aspect_ratio_menu_1781898704.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_chip_detect_before_aspect_ratio_menu_1781899161.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_chip_detect_before_duration_menu_1781899164.png`

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

- Content Brain handoff unavailable; using build_continuity_prompts()
- story progression audit flagged weak discovery/escalation/payoff separation
- screenshot failed (chip_popover_open_image_count_menu): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_option_before_image_count_menu_image_count_1): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_option_after_image_count_menu_image_count_1): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_detect_after_image_count_menu_attempt_1): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_popover_open_image_quality_menu): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_option_before_image_quality_menu_image_quality_2k): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_option_after_image_quality_menu_image_quality_2k): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_detect_after_image_quality_menu_attempt_1): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (starter_chips_initial): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_detect_before_image_count_menu): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_detect_before_image_quality_menu): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (starter_chips_verified): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (starter_image_preclean): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (latest_image_after_use_to_video): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (used_image_card_cleanup_deferred): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_popover_open_duration_menu): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_option_before_duration_menu_duration_10s): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_option_after_duration_menu_duration_10s): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_detect_after_duration_menu_attempt_1): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (video_chips_initial): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_detect_before_aspect_ratio_menu): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_detect_before_duration_menu): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (video_chips_prepared): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (video_chips_initial): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_detect_before_aspect_ratio_menu): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_detect_before_duration_menu): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (video_chips_prepared): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (video_chips_initial): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_detect_before_aspect_ratio_menu): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (chip_detect_before_duration_menu): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

- screenshot failed (video_chips_prepared): Page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded


## Screenshots

- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_chip_detect_before_image_aspect_ratio_menu_1781898393.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_chip_detect_before_image_count_menu_1781898397.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_chip_detect_before_image_quality_menu_1781898525.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_chip_detect_before_image_aspect_ratio_menu_1781898704.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_latest_image_before_scroll_1781899081.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_latest_image_after_scroll_1781899084.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_latest_image_app_menu_open_1781899087.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_latest_image_use_to_video_before_image_use_to_vi_1781899091.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_latest_image_use_to_video_after_image_use_to_vid_1781899094.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_use_starter_image_for_video_ok_1781899129.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_chip_detect_before_aspect_ratio_menu_1781899161.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_chip_detect_before_duration_menu_1781899164.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781899677.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781899722.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781899767.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781899815.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781899863.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781899912.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781899961.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781900011.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781900060.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781900109.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781900158.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781900230.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781900280.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781900329.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781900384.png`
- `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runway_live_smoke_artifacts\acf_test_01_20260619T194627_3e1aa9d2_strict_completion_pending_clip_1_1781900446.png`

## Safety Confirmation

| Gate | Value |
|------|-------|
| simulate | False |
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
