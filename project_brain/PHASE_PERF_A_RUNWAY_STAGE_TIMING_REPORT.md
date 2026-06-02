# PHASE PERF-A — Runway Stage Timing

**Date:** 2026-05-31  
**Goal:** Measure and report exact duration between Generate click, video visible in UI, URL detected, download start, and download complete.

---

## Stages (per clip)

| Stage key | Label |
|-----------|--------|
| `generate_click` | Generate Click |
| `video_visible_in_ui` | Video Visible in Runway UI |
| `url_detected` | URL Detected |
| `download_start` | Download Start |
| `download_complete` | Download Complete |

Timestamps use `time.monotonic()` (first mark wins). Wall-clock ISO times are derived from `generate_click` when session observability is enabled.

---

## Reported durations (seconds)

| Interval | Meaning |
|----------|---------|
| Generate Click → Video Visible | Runway shows real output in the DOM (non-placeholder `<video>`) |
| Video Visible → URL Detected | Wait loop accepts a real URL (new source or stable fallback) |
| URL Detected → Download Start | Orchestrator hands off to `RunwayDownloadProvider` |
| Download Start → Download Complete | HTTP download + `finalize_download_artifact` |
| Generate Click → Download Complete | End-to-end clip pipeline |

---

## Implementation

| Module | Role |
|--------|------|
| `content_brain/execution/runway_perf_timestamps.py` | Stage constants, `mark_stage`, `build_perf_report`, `format_perf_report_lines` |
| `content_brain/execution/runway_browser_observability.py` | `mark_perf_stage`, `record_perf_report`, session `perf_clips[]` |
| `providers/runway_browser_provider.py` | `log_generate_clicked()` → `generate_click` |
| `orchestrators/runway_browser_orchestrator.py` | Video visible / URL detected in wait; download start/complete; per-clip `clip_obs` |
| `project_brain/report_perf_a_runway_timings.py` | CLI report from session |
| `project_brain/validate_perf_a_runway_stage_timestamps.py` | Unit validation |

**Logs:** `[RUNWAY_PERF] stage=…` during run; full table printed at clip end via `record_perf_report()`.

**Session JSON:** `execution_runtime.operations.runway_browser_obs.perf_clips[].perf_timestamps`

---

## How to read a live UAT

After a `runway_browser` UAT session completes:

```bash
python project_brain/report_perf_a_runway_timings.py --session-id exec_uat_YYYYMMDD_HHMMSS
```

Example synthetic shape (`--demo`):

```text
=== Runway PERF-A clip 1 ===
  Generate Click: 2023-11-14T22:13:20
  Video Visible in Runway UI: 2023-11-14T22:13:32
  URL Detected: 2023-11-14T22:13:45
  Download Start: 2023-11-14T22:13:57
  Download Complete: 2023-11-14T22:14:10
  --- stage durations (seconds) ---
  Generate Click → Video Visible in Runway UI: 12.500s
  ...
```

---

## Pre-instrumentation sessions

Sessions captured **before** PERF-A (e.g. `exec_uat_20260602_190032`) do not contain `perf_clips`. Re-run 40s UAT to populate timings.

---

## Validation

```bash
python project_brain/validate_perf_a_runway_stage_timestamps.py
```

---

## Notes

- **Video visible** requires a **real** output URL (12J-E1 classifier); empty-state placeholders do not start this timer.
- **URL detected** fires when the wait loop returns an accepted URL, not merely when a `<video>` tag exists.
- Multi-clip runs store one `perf_timestamps` object per `clip_index`.
