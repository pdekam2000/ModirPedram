# PWMAP RUNWAY AGENT ADAPTER REPORT

Generated: 2026-06-23

## Why this adapter was added

ModirAgentOS internal Kling/Runway live engines (`kling_frame_to_video_live_engine`, `kling_product_run`, continuity chains) became complex and fragile for **product generation**. The **pwmap** project already mapped Runway UI and successfully generated videos via `runway_agent.py`.

**Decision:** Use pwmap as the external execution engine for Product Studio Create Video (Runway/Kling), without deleting legacy internal runtimes (diagnostics only).

## Architecture

```
ModirAgentOS Create Video
  → ProductStudioService.create_video_generate
  → provider_runtime = pwmap_agent (default for Kling native audio)
  → pwmap_runway_agent_adapter.build_pwmap_job_from_preflight()
  → subprocess: python pwmap/runway_agent.py --job agent_inbox/job.json
  → read pwmap/runway_downloads/last_result.json
  → copy MP4(s) → outputs/pwmap_agent_runs/<run_id>/
  → Results page via load_pwmap_agent_run_results()
```

Override legacy internal path: `provider_runtime=legacy_internal` in Create Video payload.

## Files created

| File | Purpose |
|------|---------|
| `content_brain/execution/pwmap_runway_agent_adapter.py` | Job build, subprocess, parse, copy, normalize |
| `project_brain/validate_pwmap_runway_agent_adapter.py` | Unit/integration validation |
| `project_brain/run_pwmap_agent_adapter_live_smoke.py` | One-clip live smoke through adapter |

## Files modified

| File | Change |
|------|--------|
| `ui/api/product_studio_service.py` | Route Kling generate to pwmap adapter; Results loader |
| `content_brain/execution/kling_product_run.py` | Marked legacy for product generation |

## Job format supported

Single clip:

```json
{
  "prompt": "...",
  "model": "Kling 3.0 Pro",
  "duration": 15,
  "aspect": "9:16",
  "native_audio": true
}
```

Multi-clip (Use Frame):

```json
{
  "prompts": ["clip1 prompt", "clip2 prompt"],
  "duration": 15,
  "aspect": "9:16",
  "use_frame_second": 14,
  "native_audio": true
}
```

## Safety

- Old internal Kling runtime **not deleted** — `LEGACY_PRODUCT_EXECUTION = True` in `kling_product_run.py`
- No secrets copied; no browser profile duplication
- Missing pwmap root → clear `PwmapAdapterError`
- pwmap root configurable via `MODIR_PWMAP_ROOT` env var (default `C:\Users\kaman\Desktop\pwmap`)

## Validation

Script: `project_brain/validate_pwmap_runway_agent_adapter.py`

Result: **ALL PASS** (31 checks)

Covers: job JSON build, subprocess command, last_result parse, MP4 copy, missing pwmap error, legacy runtime preserved, Product Studio wiring, normalized result loader.

## Live smoke

- **mode:** live
- **run_id:** `pwmap_20260623T200804_256fb07a`
- **status:** completed
- **ok:** True
- **final MP4:** `C:/Users/kaman/Desktop/ModirAgentOS/outputs/pwmap_agent_runs/pwmap_20260623T200804_256fb07a/video.mp4`
- **output folder:** `C:/Users/kaman/Desktop/ModirAgentOS/outputs/pwmap_agent_runs/pwmap_20260623T200804_256fb07a`
- **subprocess command:** `python C:\Users\kaman\Desktop\pwmap\runway_agent.py --job C:\Users\kaman\Desktop\pwmap\agent_inbox\job.json`
- **elapsed:** ~16 minutes (real Kling 15s generation via pwmap)

## Product UI integration recommendation

1. **Default:** Kling native audio Create Video uses `provider_runtime=pwmap_agent` automatically (already wired in `create_video_generate`).
2. **Results page:** Loads `pwmap_*` run IDs from `outputs/pwmap_agent_runs/` — no UI rewrite required.
3. **Developer override:** Pass `provider_runtime: "legacy_internal"` to force old internal engine for diagnostics.
4. **Env:** Set `MODIR_PWMAP_ROOT` if pwmap is not at the default desktop path.
5. **Optional UI label:** Show `provider_runtime` and `execution_engine` in Results panel (future, non-blocking).

## Output layout

```
outputs/pwmap_agent_runs/<run_id>/
  job.json
  last_result.json
  clip_1.mp4
  video.mp4
  normalized_result.json
  subprocess_stdout.log (on live run)
```