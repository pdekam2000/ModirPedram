# Kling Frame Generate Approval State — Fix Report

**Phase:** KLING-FRAME-GENERATE-APPROVAL-STATE-FIX  
**Status:** FIXED — validation PASS  
**Date:** 2026-06-18

---

## 1. Problem

Kling Frame-to-Video generate returned **failed** before live Generate ran when approval was incomplete or prerequisites blocked execution:

```
approved_by: "pop"
approval_required: false
generate_clicked: false
status: failed
native_audio_status: failed
```

Expected: missing approval → `awaiting_approval` with `approval_required: true`; prep-only blocks → `planned` native audio, not `failed`.

---

## 2. Files Changed

| File | Change |
|------|--------|
| `content_brain/execution/kling_product_run.py` | Unified approval gate; `_resolve_kling_execution_outcome()`; no `failed` before Generate |
| `content_brain/execution/kling_frame_continuity_runtime.py` | Missing starter frame → `prepared`, not `failed` |
| `content_brain/execution/kling_frame_to_video_live_engine.py` | Missing approval flags → `awaiting_approval`, not `_fail` |
| `ui/web/src/pages/CreateVideoPage.tsx` | Send `approve_generate` only when fully approved; handle `prepared` / `approval_required` |
| `project_brain/validate_kling_frame_generate_approval_state_fix.py` | New validation suite |
| `project_brain/validate_kling_full_product_integration.py` | Updated partial-approval expectation |

---

## 3. Exact Fix

### Approval gate (`kling_product_run.py`)

- `_kling_approval_complete()` requires `approve_generate`, non-empty `approved_by`, and `confirm_credit_spend`.
- Incomplete approval → `status: awaiting_approval`, `approval_required: true`, `native_audio_status: planned`, `generate_clicked: false`.
- Removed `status: approval_required` / `ok: false` path for partial approval.

### Post-execution status

- `_resolve_kling_execution_outcome()` sets `failed` / `native_audio_status: failed` only when Generate was actually attempted.
- Pre-execution blocks (missing starter frame, CDP prep) → `status: prepared`, `native_audio_status: planned`.

### Frame continuity runtime

- Missing starter frame on clip 1 → `STATUS_PREPARED` with `precondition: starter_frame_required` instead of empty `STATUS_FAILED` report.

### Live engine

- Missing `approved_by` or `confirm_credit_spend` at Generate gate → `awaiting_approval` (dry-run), not `failed`.

### UI

- `approve_generate` sent only when operator name + credit checkbox are both set.
- Treats `prepared`, `approval_required`, and non-failed pre-execution responses as awaiting-approval UX.

---

## 4. Validation Results

```bash
python project_brain/validate_kling_frame_generate_approval_state_fix.py
```

| Test | Result |
|------|--------|
| Kling frame generate without approval → awaiting_approval | **PASS** |
| Kling frame generate with approved_by only → awaiting_approval | **PASS** |
| Kling frame generate with approve + confirm + approved_by → proceeds | **PASS** |
| native_audio_status not failed before execution | **PASS** |
| generate_clicked false only when not executed | **PASS** |
| Runway approval behavior unchanged | **PASS** |
| Multishot fallback unchanged | **PASS** |

Regression:

```bash
python project_brain/validate_kling_full_product_integration.py  # PASS (approval gate updated)
python project_brain/validate_kling_preflight_schema_mismatch_fix.py  # PASS
```

---

## 5. Confirmations

| Item | Status |
|------|--------|
| Frame-to-Video remains primary Kling path | **Unchanged** |
| Multishot fallback approval gate | **Unchanged** |
| Runway generate path | **Unchanged** |
| No credits spent in validation | **Confirmed** — mocked execution where needed |

---

## 6. Operator check

| Risk | Level |
|------|-------|
| False “awaiting” when real failure after Generate | **Low** — `generate_attempted` guard |
| Runway regression | **Low** — Kling gate isolated |
| UI stuck on prepared state | **Low** — message surfaced in run status |
