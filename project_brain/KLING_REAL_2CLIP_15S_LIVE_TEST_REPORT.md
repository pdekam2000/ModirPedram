# KLING REAL 2-CLIP 15S LIVE TEST REPORT

Generated: 2026-06-20T14:39:19.124692+00:00

## Summary

- **run_id:** `kling_ft_20260620T142917_4b4c84b0`
- **browser visible:** yes (controlled Chrome via CDP port 9222, not headless)
- **clip 1 generated:** pass
- **clip 2 generated:** fail
- **aspect ratio 9:16:** pass
- **duration 15s:** fail
- **native audio option detected:** no
- **credits spent estimate:** unknown / not confirmed in artifacts
- **download result:** failed
- **downloaded paths:** 1 file(s)

## Constraints

- max clips: 2
- max generate clicks: 2 (no auto-retry)
- provider: kling / model: kling-3.0 / aspect: 9:16 / 15s per clip / total 30s

## Bridge

- start ok: True
- poll status: failed
- chain_complete: False
- continuity_status: stopped

## Clip 1

- path: `C:\Users\kaman\Desktop\ModirAgentOS\outputs\kling_frame_to_video\kling_ft_20260620T142917_4b4c84b0\clips\c1\live_run_result.json`
- ok: True
- status: download_failed
- generate_clicked: False
- aspect step: None — None
- duration step: None — None
- audio step: None — None
- output: none

## Clip 2

- path: `C:\Users\kaman\Desktop\ModirAgentOS\outputs\kling_frame_to_video\kling_ft_20260620T142917_4b4c84b0\clips\c2\live_run_result.json`
- ok: False
- status: failed
- generate_clicked: False
- use frame continuity: use_frame
- aspect/duration/audio: aspect=None, duration=None, audio=None
- output: none

## Failed steps

- clip1 step recover verify: Recovered file is not a real MP4
- clip2 step 02 provider_kling_3_pro: Kling 3.0 Pro not found: Unable to locate provider_kling_3_pro — tried 5 strategies: role_button_kling_3_pro: Locator.wait_for: Timeout 8000ms exceeded.
Call log:
  - waiting for get_by_role("button", name=re.compile(r"Kling 3\.0 Pro", re.IGNORECASE)).first to be visible
 | text_kling_3_pro: Locator.wait_for: Timeout 8000ms exceeded.
Call log:
  - waiting for locator("button:has-text(\"Kling 3.0 Pro\")").first to be visible
 | role_button_video_models: Locator.wait_for: Timeout 8000ms exceeded.
Call log:
  - waiting for get_by_role("button", name=re.compile(r"Video models", re.IGNORECASE)).first to be visible
 | map_css_stable: Locator.wait_for: Timeout 8000ms exceeded.
Call log:
  - waiting for locator("button:has-text(\"Kling 3.0 Pro\")").first to be visible

- Kling 3.0 Pro not found: Unable to locate provider_kling_3_pro — tried 5 strategies: role_button_kling_3_pro: Locator.wait_for: Timeout 8000ms exceeded.
Call log:
  - waiting for get_by_role("button", name=re.compile(r"Kling 3\.0 Pro", re.IGNORECASE)).first to be visible
 | text_kling_3_pro: Locator.wait_for: Timeout 8000ms exceeded.
Call log:
  - waiting for locator("button:has-text(\"Kling 3.0 Pro\")").first to be visible
 | role_button_video_models: Locator.wait_for: Timeout 8000ms exceeded.
Call log:
  - waiting for get_by_role("button", name=re.compile(r"Video models", re.IGNORECASE)).first to be visible
 | map_css_stable: Locator.wait_for: Timeout 8000ms exceeded.
Call log:
  - waiting for locator("button:has-text(\"Kling 3.0 Pro\")").first to be visible

## Artifacts

- run dir: `C:\Users\kaman\Desktop\ModirAgentOS\outputs\kling_frame_to_video\kling_ft_20260620T142917_4b4c84b0`
- bridge report keys: chain_complete, clip_results, clips_completed, continuity_chain, download_dir, download_report, downloaded_file_paths, errors, final_video_path, generation_report, ok, provider, status
