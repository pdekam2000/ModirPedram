# CONTINUITY DIRECTOR V1 LIVE SMOKE REPORT

Generated: 2026-06-20T21:43:44.774234+00:00

## Summary

- **run_id:** `kling_ft_20260620T213021_045937a3`
- **clip 1 generated:** yes
- **clip 1 MP4 recovered/downloaded:** no
- **last frame extracted:** no
- **PNG uploaded for clip 2:** no
- **clip 2 generated:** no
- **clip 2 MP4 recovered/downloaded:** no
- **final status:** fail
- **failure point:** clip 1: mp4_missing_or_invalid

## Topic Guard

- **passed:** True
- **starter_image_prompt chars:** 745

## MP4 recovery (Clip 1)

- **methods attempted:** recover_kling_frame_output, artifact_card_cdp_urls, _method_scoped_card_browser_download, page_video_sources:1, page_video_sources:2, page_video_sources:3, page_video_sources:4, page_video_sources, global_ui_download
- **quarantined:** ['C:/Users/kaman/Desktop/ModirAgentOS/outputs/kling_frame_to_video/kling_ft_20260620T213021_045937a3/clips/c1/quarantine/invalid_20260620T213944_page_video_1.mp4', 'C:/Users/kaman/Desktop/ModirAgentOS/outputs/kling_frame_to_video/kling_ft_20260620T213021_045937a3/clips/c1/quarantine/invalid_20260620T213944_page_video_2.mp4', 'C:/Users/kaman/Desktop/ModirAgentOS/outputs/kling_frame_to_video/kling_ft_20260620T213021_045937a3/clips/c1/quarantine/invalid_20260620T213944_page_video_3.mp4', 'C:/Users/kaman/Desktop/ModirAgentOS/outputs/kling_frame_to_video/kling_ft_20260620T213021_045937a3/clips/c1/quarantine/invalid_20260620T213944_page_video_4.mp4']
- **final path:** `none`
- **failure reason:** no_real_mp4_after_recovery methods=recover_kling_frame_output, artifact_card_cdp_urls, _method_scoped_card_browser_download, page_video_sources:1, page_video_sources:2, page_video_sources:3, page_video_sources:4, page_video_sources, global_ui_download

## MP4 recovery (Clip 2)

- **methods attempted:** none
- **final path:** `none`

## Constraints

- continuity method: last_frame_extract_upload (no Use Frame)
- max clips: 2
- max generate clicks: 2
- provider: Kling 3.0 Pro via Frame-to-Video live engine
- aspect: 9:16 / 15s per clip

## Preflight

- passed: True
- message: ok
- BROWSER_AVAILABLE: pass — CDP port reachable at 127.0.0.1:9222
- BROWSER_PROFILE: pass — Browser profile path exists: C:\Users\kaman\Desktop\ModirAgentOS\storage\real_chrome_profile
- BROWSER_AUTOMATION_READY: pass — Playwright CDP attach OK (browser version: 149.0.7827.54)
- BROWSER_SESSION_VALID: pass — CDP attach succeeded (session assumed valid if attach works)
- DOWNLOAD_PATH_READY: pass — Download path writable: C:\Users\kaman\Desktop\ModirAgentOS\downloads

## Chain

- status: stopped
- clips_completed: 0
- generate_clicks: 1
- stop_reason: mp4_missing_or_invalid
- stopped_at_clip: 1
- chain_path: `C:/Users/kaman/Desktop/ModirAgentOS/outputs/continuity_director_v1/kling_ft_20260620T213021_045937a3/continuity_director_chain.json`

## Clip 1

- generate_clicked: True
- mp4_path: `none`
- last_frame_path: `none`
- live status: download_failed
- errors: ['Could not download real MP4', 'mp4_missing_or_invalid', 'no_real_mp4_after_recovery methods=recover_kling_frame_output, artifact_card_cdp_urls, _method_scoped_card_browser_download, page_video_sources:1, page_video_sources:2, page_video_sources:3, page_video_sources:4, page_video_sources, global_ui_download']

## Clip 2

- first_frame_input_path: `none`
- generate_clicked: None
- mp4_path: `none`
- live status: n/a
- first_frame_uploaded: False
- errors: []

## Artifacts

- agent run dir: `C:\Users\kaman\Desktop\ModirAgentOS\outputs\continuity_director_v1\kling_ft_20260620T213021_045937a3`
- live engine run dir: `C:\Users\kaman\Desktop\ModirAgentOS\outputs\kling_frame_to_video\kling_ft_20260620T213021_045937a3`
