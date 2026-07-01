# Continuity Director V1 Report

Generated: 2026-06-20

## Goal

Build a clean continuity agent that chains Kling/Runway clips using **last-frame PNG extraction + file upload** — the method that succeeded in the June 17 multishot live run — without Use Frame, Image-tab recovery, or browser state guessing.

## Decision

| Approach | Status |
|----------|--------|
| Last frame extract → PNG upload | **Primary** |
| Runway Use Frame | **Excluded** |
| Image tab / continuity_frame_in_ui | **Excluded** |
| Chain without real MP4 | **Blocked** |

## Deliverable

**File:** `agents/continuity_director_agent.py`  
**Version:** `continuity_director_v1`  
**Continuity method:** `last_frame_extract_upload`

## Responsibilities

| Function | Purpose |
|----------|---------|
| `plan_clip_chain()` | Build multi-clip plan via frame planner; preserve character, environment, camera, mood per clip |
| `validate_real_mp4()` | Reject fake/placeholder MP4s (`verify_recovered_mp4`) |
| `prepare_next_clip_first_frame()` | ffmpeg last frame → `continuity/frame_cN.png` |
| `ContinuityDirectorAgent.run_chain()` | Orchestrate generate → MP4 gate → extract → next clip input |
| `build_frame_live_generate_hook()` | Optional live hook: `run_kling_frame_to_video_live` with **file upload only** (`continuity_frame_in_ui=False`) |
| `build_frame_live_recover_hook()` | Optional live recovery via `recover_kling_frame_output` |

## Flow

```
For each clip N in plan:
  1. If N > 1: require prior continuity PNG on disk
  2. Generate clip N (injectable hook; max 1 click per clip)
  3. Recover MP4 if needed (optional hook)
  4. Validate real MP4 — stop if missing/invalid
  5. If N < clip_count: extract last frame PNG
  6. Pass PNG path as first_frame_path for clip N+1
```

Clip 1 uses prompt-only (text-to-video). Clip 2+ receives **`continuity/frame_c{N-1}.png`** via file upload — same pattern as `kling_ms_20260617T181055` success run.

## Safety rules

- No Use Frame calls in agent source
- No `continuity_frame_in_ui`
- Fake MP4 quarantined under `clips/cN/quarantine/`
- Chain stops on: missing MP4, invalid MP4, extract failure, missing PNG for next clip
- `generate_clicks` capped by `clip_count`

## Stable code reused (not duplicated)

| Module | Use |
|--------|-----|
| `kling_frame_to_video_planner` | Clip plan + story metadata |
| `kling_last_frame_extractor` | Last frame PNG extraction |
| `kling_multishot_live_engine.verify_recovered_mp4` | MP4 validation |
| `kling_frame_to_video_live_engine` | Live generate/recover hooks only |

## Output artifacts

```
{run_dir}/
  continuity_director_chain.json
  continuity/continuity_director_chain.json
  continuity/frame_c1.png
  clips/c1/video.mp4
  clips/c2/video.mp4
```

## Validation

```powershell
cd C:\Users\kaman\Desktop\ModirAgentOS
python project_brain/validate_continuity_director_v1.py
```

| Test | Coverage |
|------|----------|
| clip plan created | 2-clip plan, continuity metadata |
| MP4 required before next clip | Single generate then stop |
| fake MP4 rejected | Quarantine + not real |
| last frame PNG extracted | ffmpeg synthetic MP4 |
| PNG passed to next clip | Clip 2 `first_frame_path` = `frame_c1.png` |
| no Use Frame | Source audit |
| chain stops when MP4 missing | `stop_reason=mp4_missing_or_invalid` |
| 2-clip dry run | Full mocked chain completes |

## Integration (future)

Wire into Product Studio or bridge as an alternative to `kling_frame_continuity_runtime` (Use Frame path):

```python
from agents.continuity_director_agent import (
    ContinuityDirectorAgent,
    plan_clip_chain,
    build_frame_live_generate_hook,
    build_frame_live_recover_hook,
)

plan = plan_clip_chain(run_id=..., topic=..., clip_count=2)
agent = ContinuityDirectorAgent(project_root)
result = agent.run_chain(
    plan=plan,
    run_dir=run_dir,
    generate_clip=build_frame_live_generate_hook(approved_by=..., confirm_credit_spend=True),
    recover_mp4=build_frame_live_recover_hook(),
)
```

Not wired in this phase — agent + validation only.

## Relation to regression audit

This agent restores the **proven June 17 continuity mechanism** (extract PNG + upload) while using the **frame-to-video live engine** for 15s single-prompt clips — avoiding the Use Frame / Image-tab failure mode documented in `KLING_WORKING_PATH_REGRESSION_AUDIT`.
