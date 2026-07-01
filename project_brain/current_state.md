# Current State

Generated: `2026-05-31 05:19:21`

## pwmap runtime (vendored)

- **Repo source:** `external/pwmap/` — canonical pwmap code in ModirAgentOS (Runway agent + download selection repair).
- **Local production default:** `C:\Users\kaman\Desktop\pwmap` when that folder exists (browser profile, downloads stay outside git).
- **Override:** set `MODIR_PWMAP_ROOT` to point at either path. Resolution logic: `content_brain/execution/pwmap_runway_agent_adapter.py`.

## Status

Runtime Editing V1 is working.

## Project Size

- Folders: `1597`
- Files: `13247`

## Runtime Summary

```json
{
  "status": "Runtime state loaded.",
  "latest_file": "runtime_20260528_191600_76bbcc63.json",
  "session_id": "runtime_20260528_191600_76bbcc63",
  "runtime_status": null,
  "current_step": null,
  "updated_at": "2026-05-28 19:16:00",
  "approval_metadata": null
}
```

## Latest Completed Work

Automatic Project Brain + Full Handoff + Backup script added:

`project_brain/auto_handoff_backup.py`
