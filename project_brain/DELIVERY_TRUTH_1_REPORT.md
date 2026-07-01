# PHASE DELIVERY-TRUTH-1 Report

**Date:** 2026-06-03  
**Status:** Complete (infrastructure + audit + archive)

## Problem

Split-brain delivery state:

- `final_delivery_registry` approved cat test run `cb_sv1_20260613_095159_5fdbc1ce`
- `runs/index.json` canonical head = dog run `cb_e2e_20260613_162423_dcde7693`
- Results UI showed manifest PASS while pipeline reported `music_inaudible_or_failed` and `subtitle_burn_failed`

Manifests and metadata could not be trusted.

## Root cause

Multiple parallel sources of truth (registry, runs index, latest attempt, asset library, story packages) were not synchronized. Approval did not require final MP4 perceptual audit.

## Changes

| Component | Change |
|-----------|--------|
| `content_brain/platform/canonical_run.py` | Single canonical run pointer |
| `content_brain/platform/delivery_truth_loader.py` | Final MP4 audit panel for Results |
| `content_brain/quality/delivery_reality_auditor.py` | `audit_final_mp4_delivery()` — MP4-only, no manifest trust |
| `content_brain/platform/final_delivery_registry.py` | Approval requires canonical run match + `delivery_reality_passed` |
| `content_brain/platform/results_run_loader.py` | Unified run_id; delivery truth overrides manifest labels |
| `ui/web/src/pages/ResultsPage.tsx` | Delivery Truth Audit PASS/FAIL panel |
| `project_brain/archive_stale_delivery_artifacts.py` | Move stale cat/recovery artifacts to archive (no delete) |
| `project_brain/run_delivery_truth_1_validation.py` | Sync + audit validation |

## Delivery truth audit (final MP4 only)

Checks on delivered MP4 pixels/audio:

- Subtitles (visible + Shorts-readable bbox height)
- Music audible
- Ambience audible
- Dialogue audible
- Voice separation (speech window coverage)
- Story quality (speech coverage heuristic)

**APPROVED only when all checks PASS on the final MP4.**

## Archive

Stale artifacts moved to:

`storage/archive/delivery_truth_1/<timestamp>/`

Includes cat test run folders, stale story packages, registry snapshots. Registry reset to `approved: false`.

## Validation

```bash
python project_brain/run_delivery_truth_1_validation.py
```

Output: `project_brain/DELIVERY_TRUTH_1_VALIDATION.json`

## New-topic full pipeline

Validation topic registered: **Sunrise coastal kayak guide for beginners**

Full Runway pipeline must be executed manually via Create Video. System will not mark APPROVED until `audit_final_mp4_delivery()` passes on the new run's final MP4.
