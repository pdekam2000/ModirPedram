# PWMAP 30s Two-Clip Live Retest #2 Report

**Phase:** PWMAP-30S-TWO-CLIP-LIVE-RETEST-2
**Date:** 2026-07-01 / 2026-07-02
**Verdict:** **PASS** — duplicate-clip bug fixed; full pipeline completed end-to-end; YouTube upload private
**Run ID (successful):** `pwmap_20260701T185423_65ea406e`

---

## Executive summary

Retest #2 required two attempts. The first live attempt (`pwmap_20260701T184242_6c83c9da` and an earlier CLI-triggered run `pwmap_20260701T182150_ed073fce`) crashed before generating any clip — a regression introduced by the download-selection repair itself, unrelated to the original duplicate-clip bug. After a targeted fix, a second live attempt (`pwmap_20260701T185423_65ea406e`), triggered from the Create Video GUI, completed the full pipeline: two distinct clips generated with Use Frame continuity, correct per-clip download, duplicate guard pass, assembly, branding, YouTube metadata, and a private YouTube auto-upload.

**Root cause of the original bug (clip 2 = clip 1) is confirmed fixed at the source (pwmap download-selection layer).**

---

## Part A — Pre-live validation

| Validator | Result |
|-----------|--------|
| `validate_pwmap_download_selection_repair` | **PASS** 23/23 |
| `validate_pwmap_30s_two_clip_duplicate_guard` | **PASS** 15/15 |
| `validate_pwmap_runway_agent_adapter` | 28/29 — `[FAIL] product_uses_pwmap` (pre-existing stale test; see note) |
| `validate_product_visual_diversity_guard` | **PASS** 12/12 |
| `validate_auto_youtube_upload_after_publish` | **PASS** 13/13 |
| `validate_youtube_upload_runtime` | **PASS** 15/15 |
| `validate_pwmap_browser_close_finalization` | 9/11 — 2 fixture-artifact failures (see note) |
| `validate_upload_agent_v1` | **PASS** 18/18 |

### Notes on non-blocking findings

- **`product_uses_pwmap` (adapter validator):** stale string-match test. It checks that `run_pwmap_product_studio_generate` appears literally in `ui/api/product_studio_service.py`. Since the `product_multiclip_orchestrator.run_product_multiclip_generate` layer was introduced (which itself calls `run_pwmap_product_studio_generate`), the direct string no longer appears in that file, even though the call path is intact and confirmed working end-to-end by the live run. Not a functional defect. Fix (optional, test-only): update the assertion in `project_brain/validate_pwmap_runway_agent_adapter.py::test_product_studio_wiring` to also check `product_multiclip_orchestrator.py`.
- **`two_clip_run_records_both_clips` / `recovery_from_source_when_local_missing`:** the test fixture in `validate_pwmap_browser_close_finalization.py` writes two byte-identical dummy MP4s (`b"\x00" * size` for both "sources"). The duplicate-clip guard now correctly identifies them as duplicates and rejects the second — this is the guard working as designed, not a regression. The fixture predates the duplicate-guard repair and needs distinct dummy content to remain meaningful; not fixed here per scope (test-only, no production code involved).

---

## Part B — Live run #1 (failed — new bug, not the original duplicate bug)

| Field | Value |
|-------|-------|
| Run ID | `pwmap_20260701T182150_ed073fce` (CLI) and `pwmap_20260701T184242_6c83c9da` (GUI) |
| Failure stage | **generation** (clip 1, immediately after clicking Generate) |
| Clips produced | 0 |
| Error | `[ERROR] 'count'` / `KeyError: 'count'` |

**Root cause:** `capture_output_snapshot()` (added for the duplicate-guard repair) returns `{"video_count": ..., "videos": [...]}`. The pre-existing `_feed_has_new_generation()` (called from `wait_for_video_ready()`, which fires right after clicking Generate) still read `baseline["count"]` / `baseline["srcs"]`, which don't exist in the new snapshot shape. This is a schema-mismatch regression from the download-selection wiring, not a resurgence of the original stale-download bug — it happened before any clip or download selection logic ran.

**Additional finding:** the pwmap runtime that actually executes is `C:\Users\kaman\Desktop\pwmap\runway_agent.py` (Desktop path takes precedence per adapter resolution order), not `external/pwmap/runway_agent.py`. A fix applied only to the vendored repo copy would not affect real runs unless mirrored to the Desktop copy.

**Fix applied** (both `C:\Users\kaman\Desktop\pwmap\runway_agent.py` and `external/pwmap/runway_agent.py`, verified byte-identical afterward — SHA256 `204c4b9a16f571e77564228a4d46589a87d7ffd4460f15c7db14bd9ce7ff4720`):

`_feed_has_new_generation()` now reads `baseline.get("video_count", baseline.get("count", 0))` and falls back to deriving `srcs` from `baseline.get("videos", [])` when the legacy `"srcs"` key is absent — compatible with both snapshot shapes. No prompt, Use Frame, YouTube, or guard logic was touched.

---

## Part C — Live run #2 (success)

| Field | Value |
|-------|-------|
| Run ID | `pwmap_20260701T185423_65ea406e` |
| Trigger | Create Video GUI, 30s / 2 clips, `free_credit_mode` |
| Status | `ok: true`, `status: completed` |
| Pipeline trace | `story_planning → clip_generation → use_frame_chain → download_verification → assembly_bridge → youtube_metadata_generation → subtitle_branding_publish → youtube_upload_runtime` — **all stages `completed`** |
| Final video duration | 30.13s |

### Clip files

| Clip | Path | Size (bytes) | SHA256 |
|------|------|---------------|--------|
| 1 | `clip_1.mp4` | 24,238,258 | `85588ca06c3ae6927ac2804dfcc9207bbba243e12d588270c999a11541c3de4a` |
| 2 | `clip_2.mp4` | 20,800,905 | `2788ea00d9c048fc1e2d71fc502ef90acc644e62ab53e191513234cfc75c8640` |

**SHA256(clip_1) ≠ SHA256(clip_2): YES.** Duplicate-download bug is fixed.

### Use Frame

`job.json`: `use_frame_second: 14`, 2 distinct prompts. Pipeline trace shows `use_frame_chain: completed`.

### Visual diversity

| Field | Value |
|-------|-------|
| `status` | `prompt_diversity_passed` |
| `repetition_risk` | `medium` |
| `visual_diversity_score` | 44 |
| `repeated_clip_warning` | `true` (legitimate warning, non-blocking) |
| `youtube_upload_allowed` | `true` |

### Assembly / branding / publish package

| Artifact | Present? |
|----------|----------|
| `publish/FINAL_PUBLISH_READY.mp4` | Yes |
| `publish/FINAL_BRANDED_PUBLISH_READY.mp4` | Yes |
| `publish/youtube_metadata.json` | Yes |
| `assembly_status` | `completed` |
| `branding_status` | `completed` |
| `publish_package_ready` | `true` |

### YouTube upload

| Field | Value |
|-------|-------|
| `uploaded` | `true` |
| `upload_status` | `uploaded` |
| `youtube_video_id` | `_GYyNxUydJE` |
| `youtube_url` | `https://www.youtube.com/watch?v=_GYyNxUydJE` |
| **`visibility`** | **`private`** |
| Channel | `Lost Signal HD` (`UCtBjz0YpU_3LG6pci6C-VXg`) |

All gates passed before upload was attempted; visibility correctly defaulted to `private`; no bypass of any guard was needed or performed.

---

## Part D — Success criteria checklist

| Criterion | Met? |
|-----------|------|
| `clip_1.mp4` exists | Yes |
| `clip_2.mp4` exists | Yes |
| SHA256(clip_1) ≠ SHA256(clip_2) | **Yes** |
| Both clips valid MP4 | Yes (24.2MB / 20.8MB, real content) |
| Visual diversity passes or legitimate warning | Yes (`prompt_diversity_passed`, medium-risk warning, non-blocking) |
| Assembly creates `FINAL_PUBLISH_READY.mp4` | Yes |
| Branding creates `FINAL_BRANDED_PUBLISH_READY.mp4` | Yes |
| `youtube_metadata.json` exists | Yes |
| YouTube auto-upload only if all gates pass | Yes |
| Upload visibility private | Yes |

**Overall phase verdict: PASS.**

---

## Artifacts

| Artifact | Path |
|----------|------|
| Successful run directory | `outputs/pwmap_agent_runs/pwmap_20260701T185423_65ea406e/` |
| Failed run (pre-fix, CLI) | `outputs/pwmap_agent_runs/pwmap_20260701T182150_ed073fce/` |
| Failed run (pre-fix, GUI) | `outputs/pwmap_agent_runs/pwmap_20260701T184242_6c83c9da/` |
| Pipeline trace | `.../pwmap_20260701T185423_65ea406e/pipeline_trace.json` |
| Visual diversity report | `.../pwmap_20260701T185423_65ea406e/visual_diversity_report.json` |
| YouTube upload result | `.../pwmap_20260701T185423_65ea406e/publish/youtube_upload_result.json` |
| Fixed runtime files | `C:\Users\kaman\Desktop\pwmap\runway_agent.py`, `external/pwmap/runway_agent.py` |

---

## Next recommended step

1. Do **not** yet proceed to 40s/three-clip continuity — per phase gating, only a 30s/two-clip PASS unlocks the next duration/clip-count phase, which this report now confirms.
2. Optional low-priority cleanup (test-only, no production risk): update the stale `product_uses_pwmap` assertion and the `validate_pwmap_browser_close_finalization` duplicate-clip test fixture to use distinct dummy content.
3. A new set of product/SEO/scheduling feature requests has been raised separately (Use Frame timing, YouTube description/tags SEO, subscribe CTA overlay, style-selection enforcement, multi-platform daily scheduling) — tracked and scoped independently of this duplicate-clip repair.
