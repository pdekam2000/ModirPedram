# UAT Run Report — `exec_uat_20260602_110110`

**Date:** 2026-06-02 11:28:28
**Status:** PASS

## Inputs

- **Topic:** cat
- **Platform:** youtube_shorts
- **Duration (s):** 10
- **Video provider:** runway_browser
- **Voice provider:** elevenlabs
- **Confirm real voice:** True
- **Confirm real assembly:** True

## Provider modes

- **Video:** `real`
- **Voice:** `real`
- **Assembly:** `real`

## Outputs

- **Artifact folder:** `C:\Users\kaman\Desktop\ModirAgentOS\storage\content_brain\execution\artifacts\exec_uat_20260602_110110`
- **Final video:** `C:\Users\kaman\Desktop\ModirAgentOS\storage\content_brain\execution\artifacts\exec_uat_20260602_110110\assembly_generation\FINAL_PUBLISH_READY.mp4`
- **Review template:** `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\user_acceptance_reviews\exec_uat_20260602_110110_review_template.json`

## Stage summary

```json
{
  "content_brain": {
    "success": true,
    "brief_id": "brief_20260602_110110_5ad5e635",
    "decision": "REVISE",
    "clip_count": 2,
    "production_ready": false
  },
  "video": {
    "success": true,
    "video_provider_mode": "real",
    "message": "Video provider dispatch completed.",
    "dispatch_reject_code": null,
    "queue_bridge": true
  },
  "voice": {
    "success": true,
    "voice_provider_mode": "real",
    "real_provider_called": true,
    "tts_executed": true,
    "code": null,
    "message": "Live voice TTS completed."
  },
  "subtitle": {
    "success": true,
    "formats_written": [
      "srt",
      "ass",
      "vtt"
    ],
    "manifest_path": "C:\\Users\\kaman\\Desktop\\ModirAgentOS\\storage\\content_brain\\execution\\artifacts\\exec_uat_20260602_110110\\subtitle_generation\\subtitle_manifest.json",
    "cue_count": 5,
    "code": null,
    "message": "Subtitle generation completed."
  },
  "assembly": {
    "success": true,
    "assembly_mode": "real",
    "real_assembly_executed": true,
    "output_created": true,
    "final_video_path": "C:\\Users\\kaman\\Desktop\\ModirAgentOS\\storage\\content_brain\\execution\\artifacts\\exec_uat_20260602_110110\\assembly_generation\\FINAL_PUBLISH_READY.mp4",
    "manifest_path": "C:\\Users\\kaman\\Desktop\\ModirAgentOS\\storage\\content_brain\\execution\\artifacts\\exec_uat_20260602_110110\\assembly_generation\\assembly_manifest.json",
    "code": null,
    "message": "Real assembly completed."
  }
}
```

## Warnings / errors

- Live voice smoke safety: duration reduced from 15s to 10s to satisfy the 11H-2d single-segment smoke cap (max 1 segment). This is a smoke safety limit, not a Content Brain failure.

## Next steps — human review

1. Watch `FINAL_PUBLISH_READY.mp4`.
2. Fill in scores (0–10) in the review template JSON.
3. Save completed review as `{session_id}_review.json` in `user_acceptance_reviews/`.
4. Do **not** publish automatically — UAT mode only.
