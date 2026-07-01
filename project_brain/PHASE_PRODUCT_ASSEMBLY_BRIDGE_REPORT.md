# PHASE PRODUCT-ASSEMBLY-BRIDGE Report

**Phase:** `PRODUCT-ASSEMBLY-BRIDGE`  
**Date:** 2026-06-27  
**Goal:** Bridge completed Product Studio pwmap runs into the existing publish assembly path.

---

## Reused Legacy Components

| Component | Path | Role |
|-----------|------|------|
| FFmpeg stitcher | `utils/ffmpeg_stitcher.py` | Multi-clip concat (`stitch_clips`) |
| Runway clip validation | `runway_live_post_processor.collect_valid_download_paths` | Non-empty file checks |
| MP4 validation | `pwmap_runway_agent_adapter.validate_mp4_path` | Size/exists gate (≥ 1 MB) |
| Runway assembly pattern | `runway_live_post_processor.run_assembly` | Reference for manifest + FFmpeg flow |
| Runway publish package | `runway_live_post_processor.run_publish_package` | Downstream subtitle/branding target (unchanged) |
| Branding canonical naming | `branding_runtime.FINAL_BRANDED_VIDEO_CANONICAL` | Future SUBTITLE-BRANDING-PUBLISH input |
| YT-1 metadata | `publish/youtube_metadata_generator.ensure_product_studio_publish_metadata` | Invoked after successful assembly (unchanged) |
| Hailuo / assembly runtime | `content_brain/execution/assembly_runtime_engine.py` | Not duplicated — Product Studio uses lightweight bridge first |

**Not modified:** duration planner, pwmap generation, Use Frame, browser mappings, timeout hardening, YouTube metadata generator internals, upload runtime.

---

## Created Files

| File | Purpose |
|------|---------|
| `content_brain/execution/product_assembly_bridge.py` | Clip discovery, validation, FFmpeg assembly, publish manifests |
| `project_brain/validate_product_assembly_bridge.py` | Validation suite (22 tests) |
| `project_brain/PHASE_PRODUCT_ASSEMBLY_BRIDGE_REPORT.md` | This report |

---

## Modified Files

| File | Change |
|------|--------|
| `content_brain/execution/product_multiclip_orchestrator.py` | Calls assembly bridge after successful pwmap run |
| `content_brain/execution/pwmap_finalization.py` | Exposes assembly/publish fields in results payload |
| `ui/api/product_studio_service.py` | Merges assembly state into Product Studio Results API |
| `ui/web/src/pages/ResultsPage.tsx` | Assembly / publish readiness display |

---

## Assembly Flow

```
pwmap run completes (clip_1..clip_N.mp4 in run folder)
        │
        ▼
discover_product_studio_clips()
  • sequential numbering
  • file exists + size > 0
  • no duplicate paths
  • single-clip fallback: video.mp4
        │
        ├─ missing clip ──► publish/assembly_manifest.json (assembly_failed)
        │                   publish/publish_metadata.json
        │                   Results: missing index + recovery flag
        │
        ▼
run_product_assembly_bridge()
  • 1 clip  → copy → publish/FINAL_PUBLISH_READY.mp4
  • 2+ clips → FFmpegStitcher → publish/FINAL_PUBLISH_READY.mp4
        │
        ▼
publish/assembly_manifest.json
publish/publish_metadata.json
        │
        ▼
ensure_product_studio_publish_metadata()  [existing YT-1, unchanged]
  • publish/youtube_metadata.json
        │
        ▼
Ready for SUBTITLE-BRANDING-PUBLISH → YT-2
```

### Publish folder layout

```
outputs/pwmap_agent_runs/<run_id>/
  clip_1.mp4 … clip_N.mp4
  publish/
    FINAL_PUBLISH_READY.mp4      ← canonical assembly output
    assembly_manifest.json
    publish_metadata.json
    youtube_metadata.json          ← from YT-1 (when assembly succeeds)
    metadata.json                  ← package index from YT-1 helper
```

### `assembly_manifest.json` (success)

```json
{
  "run_id": "pwmap_…",
  "clip_count": 4,
  "input_clips": ["…/clip_1.mp4", "…/clip_2.mp4", "…"],
  "assembly_status": "completed",
  "output_video": "…/publish/FINAL_PUBLISH_READY.mp4"
}
```

### Failure (example: clip 3 missing of 4)

```json
{
  "assembly_status": "assembly_failed",
  "missing_clip_indices": [3, 4],
  "available_clip_indices": [1, 2],
  "recovery_possible": true
}
```

No silent continuation when expected clips are missing.

---

## Validation Results

```powershell
python project_brain\validate_product_assembly_bridge.py
```

**Result: 22/22 PASS**

| Test | Result |
|------|--------|
| 2 / 3 / 4 clip assembly | PASS |
| Clips sorted sequentially | PASS |
| Manifest + publish folder created | PASS |
| `FINAL_PUBLISH_READY.mp4` created | PASS |
| Missing clip → `assembly_failed` | PASS |
| Recovery flag + no silent continue | PASS |
| YT-1 consumes publish output | PASS |
| Provider logic untouched | PASS |

---

## Publish Package Behavior

- **Success:** `publish_package_ready: true`, `assembly_status: completed`
- **Failure:** `publish_package_ready: false`, `assembly_status: assembly_failed`
- **Downstream markers:** `publish_metadata.downstream_ready` lists subtitle, branding, YouTube, TikTok, Instagram runtimes
- **Results API fields:** `assembly_complete`, `final_publish_video_path`, `source_clip_count`, `publish_package_path`, `missing_clip_index`, `assembly_recovery_possible`

---

## Results UI

Product Multi-Clip Output panel now shows:

- Assembly complete / failed
- Publish package ready
- Source clip count
- Final publish video path
- Publish folder path
- On failure: missing clip index + recovery possible

---

## Next Recommended Phase

### 1. PHASE SUBTITLE-BRANDING-PUBLISH

Wire `publish/FINAL_PUBLISH_READY.mp4` into:

- Subtitle burn-in runtime
- Branding runtime → `FINAL_BRANDED_VIDEO_CANONICAL.mp4`
- Full Runway-style publish package completion

### 2. PHASE YT-2 — YouTube Upload Runtime

OAuth, upload, scheduling, thumbnail upload, privacy settings — using existing `youtube_metadata.json`.

### Optional backfill

Existing successful pwmap runs with all clips on disk can be reassembled by calling `run_product_assembly_bridge()` against their run folder (no regeneration required).
