# KLING 2-CLIP USE FRAME LIVE TEST REPORT

Generated: 2026-06-23T19:49:08.304871+00:00

## Summary

- **run_id:** `kling_uf_20260623T194151_eed4c82a`
- **FINAL STATUS:** SUCCESS
- **continuity method:** use_frame
- **fallback used:** False
- **chain complete:** True
- **distinct clips verified:** clip1 SHA256 ≠ clip2 SHA256
- **generation completion gate:** clip2 waited ~335s for new artifact

## Clip 1

- **generation status:** completed
- **generate clicked:** True
- **generation completed:** True
- **mp4 path:** `C:\Users\kaman\Desktop\ModirAgentOS\outputs\kling_frame_to_video\kling_uf_20260623T194151_eed4c82a\clips\c1\video.mp4`
- **recovery methods:** ['live_result.clip_output_path']

## Use Frame handoff

- clip None: method=use_frame status=activated ok=None
- clip None: method=use_frame status=clip_generated ok=None

## Clip 2

- **generation status:** completed
- **generate clicked:** True
- **generation completed:** True
- **mp4 path:** `C:\Users\kaman\Desktop\ModirAgentOS\outputs\kling_frame_to_video\kling_uf_20260623T194151_eed4c82a\clips\c2\video.mp4`
- **recovery methods:** ['live_result.clip_output_path']

## Merged output

- **path:** `C:\Users\kaman\Desktop\ModirAgentOS\outputs\kling_2clip_useframe\kling_uf_20260623T194151_eed4c82a\merged_30s.mp4`
- **merge detail:** ffmpeg_concat

## Errors

- continuity: complete

## Artifacts

- output dir: `C:\Users\kaman\Desktop\ModirAgentOS\outputs\kling_2clip_useframe\kling_uf_20260623T194151_eed4c82a`
- live engine dir: `C:\Users\kaman\Desktop\ModirAgentOS\outputs\kling_frame_to_video\kling_uf_20260623T194151_eed4c82a`
- download report status: completed
