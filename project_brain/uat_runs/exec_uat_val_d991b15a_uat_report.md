# UAT Run Report — `exec_uat_val_d991b15a`

**Date:** 2026-06-01 19:26:19
**Status:** PASS

## Inputs

- **Topic:** 12D validator mock topic
- **Platform:** youtube_shorts
- **Duration (s):** 30
- **Video provider:** mock
- **Voice provider:** mock
- **Confirm real voice:** False
- **Confirm real assembly:** False

## Provider modes

- **Video:** `mock`
- **Voice:** `mock`
- **Assembly:** `mock`

## Outputs

- **Artifact folder:** `C:\Users\kaman\Desktop\ModirAgentOS\storage\content_brain\execution\artifacts\exec_uat_val_d991b15a`
- **Final video:** `C:\Users\kaman\Desktop\ModirAgentOS\storage\content_brain\execution\artifacts\exec_uat_val_d991b15a\assembly_generation\FINAL_PUBLISH_READY.mp4`
- **Review template:** `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\user_acceptance_reviews\exec_uat_val_d991b15a_review_template.json`

## Stage summary

```json
{
  "content_brain": {
    "success": true,
    "brief_id": "brief_20260601_192618_2e9fdd69",
    "decision": "PROCEED",
    "clip_count": 3,
    "production_ready": true
  },
  "video": {
    "success": true,
    "video_provider_mode": "mock",
    "message": "Mock video clips generated via FFmpeg lavfi.",
    "clip_count": 3,
    "clip_paths": [
      "C:\\Users\\kaman\\Desktop\\ModirAgentOS\\storage\\content_brain\\execution\\artifacts\\exec_uat_val_d991b15a\\video_generation\\clip_001.mp4",
      "C:\\Users\\kaman\\Desktop\\ModirAgentOS\\storage\\content_brain\\execution\\artifacts\\exec_uat_val_d991b15a\\video_generation\\clip_002.mp4",
      "C:\\Users\\kaman\\Desktop\\ModirAgentOS\\storage\\content_brain\\execution\\artifacts\\exec_uat_val_d991b15a\\video_generation\\clip_003.mp4"
    ],
    "manifest_path": "C:\\Users\\kaman\\Desktop\\ModirAgentOS\\storage\\content_brain\\execution\\artifacts\\exec_uat_val_d991b15a\\video_generation\\video_manifest.json"
  },
  "voice": {
    "success": true,
    "voice_provider_mode": "mock",
    "real_provider_called": false,
    "tts_executed": true,
    "code": null,
    "message": "Mock live voice TTS completed."
  },
  "subtitle": {
    "success": true,
    "formats_written": [
      "srt",
      "ass",
      "vtt"
    ],
    "manifest_path": "C:\\Users\\kaman\\Desktop\\ModirAgentOS\\storage\\content_brain\\execution\\artifacts\\exec_uat_val_d991b15a\\subtitle_generation\\subtitle_manifest.json",
    "cue_count": 15,
    "code": null,
    "message": "Subtitle generation completed."
  },
  "assembly": {
    "success": true,
    "assembly_mode": "mock",
    "final_video_path": "C:\\Users\\kaman\\Desktop\\ModirAgentOS\\storage\\content_brain\\execution\\artifacts\\exec_uat_val_d991b15a\\assembly_generation\\FINAL_PUBLISH_READY.mp4",
    "manifest_path": "C:\\Users\\kaman\\Desktop\\ModirAgentOS\\storage\\content_brain\\execution\\artifacts\\exec_uat_val_d991b15a\\assembly_generation\\assembly_manifest.json",
    "real_assembly_executed": false
  }
}
```

## Warnings / errors


## Next steps — human review

1. Watch `FINAL_PUBLISH_READY.mp4`.
2. Fill in scores (0–10) in the review template JSON.
3. Save completed review as `{session_id}_review.json` in `user_acceptance_reviews/`.
4. Do **not** publish automatically — UAT mode only.
