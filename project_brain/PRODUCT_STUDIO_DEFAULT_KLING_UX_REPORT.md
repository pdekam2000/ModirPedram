# Product Studio Default Kling UX — Report

**Phase:** PRODUCT-STUDIO-DEFAULT-KLING-UX + KLING_FRAME_GUI_STARTER_FRAME_WIRING  
**Status:** IMPLEMENTED — validation PASS  
**Date:** 2026-06-18

---

## Summary

Product Studio now defaults to Kling Frame-to-Video with one-click Generate: type topic → click Generate Video. Operator approval form removed; approval auto-filled internally. Last topic persists across reloads. Starter frame auto-generated before live runtime.

---

## Files Changed

| File | Change |
|------|--------|
| `content_brain/product_settings/last_topic_store.py` | New — persists last topic JSON |
| `content_brain/execution/kling_product_run.py` | `ensure_kling_starter_frame_path()`, auto starter before execute |
| `ui/api/product_studio_service.py` | Last topic API, Kling auto-approval defaults |
| `ui/api/main.py` | `GET/PUT /product/last-topic` |
| `ui/web/src/api/productClient.ts` | `fetchLastTopic`, `saveLastTopic` |
| `ui/web/src/product/constants.ts` | Kling provider listed first |
| `ui/web/src/pages/CreateVideoPage.tsx` | Kling defaults, topic persistence, no approval UI, simplified Generate |
| `project_brain/validate_product_studio_default_kling_ux.py` | Validation suite |

---

## UX Fixes

### FIX 1 — Remove approval form
- Removed operator name + credit checkbox from GUI
- Generate sends: `approve_generate: true`, `approved_by: "product_studio"`, `confirm_credit_spend: true`
- Backend applies same defaults via `_apply_product_studio_kling_defaults()`

### FIX 2 — Remember last topic
- Storage: `project_brain/product_settings/last_topic.json`
- API: `GET/PUT /product/last-topic`
- UI loads on mount; saves on blur + Generate

### FIX 3 — Kling defaults
- Provider: `kling_3_0_pro_native_audio`
- Audio strategy: `kling_native_audio`
- Generation mode: `kling_frame_to_video_native_audio` (via preflight routing)
- Runway remains selectable

### FIX 4 — One-click Generate workflow
Generate now automatically:
1. Saves topic
2. Runs preflight (inside `create_video_generate`)
3. Auto-approves Kling run
4. Generates starter frame locally (PIL, no credits)
5. Passes `first_frame_path` to frame continuity runtime
6. Invokes live Kling frame engine (CDP when available)

---

## Validation

```bash
python project_brain/validate_product_studio_default_kling_ux.py
```

| Test | Result |
|------|--------|
| Kling default provider | PASS |
| Kling Native Audio default strategy | PASS |
| Last topic persists | PASS |
| Topic restored correctly | PASS |
| Generate without approval form | PASS |
| approved_by auto-filled | PASS |
| confirm_credit_spend auto-filled | PASS |
| Starter frame auto-generated | PASS |
| Generate reaches live runtime | PASS |
| Runway optional path | PASS |

---

## Operator Flow

```
Open Product Studio → topic restored → click Generate Video
```

No approval form. No manual starter frame. No separate preflight required (optional Preflight Plan button retained for preview).

---

## Notes

- Live Generate still requires Runway CDP browser on `http://127.0.0.1:9222`
- Starter frame uses local PIL render (no Runway credits)
- `approval.json` now records `execution_status` separately from approval outcome
