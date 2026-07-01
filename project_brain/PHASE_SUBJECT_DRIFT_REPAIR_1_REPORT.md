# PHASE SUBJECT-DRIFT-REPAIR-1 — Fail-Closed Run Isolation Report

**Date:** 2026-06-03  
**Phase:** SUBJECT-DRIFT-REPAIR-1  
**Status:** Complete

---

## Root cause

A new Create Video run (`cb_e2e_20260613_120215_7eda6674`, topic: *fantezy girl and man talking together in park*) failed at Runway with **0 clips downloaded**. Despite that:

- Prompt builder and visual memory correctly used the **park** topic.
- **Results**, `final_delivery_registry`, story packages, and voice registry still reflected the **previous approved cartoon cat run** (`cb_sv1_20260613_095159_5fdbc1ce`, Whiskers/Sage).
- `results_run_loader.py` raised **`NameError: collect_valid_download_paths`**, breaking `/product/results/latest`.
- There was **no isolated run context** per Create Video request and **no separate “latest attempt”** record, so the UI could present stale approved output as if it belonged to the new run.

This was a **split-brain / subject drift** failure mode: generation layer used the new topic; delivery and Results layers fell back to prior approved artifacts.

---

## Files changed

| File | Change |
|------|--------|
| `content_brain/platform/run_isolation.py` | **New** — run context, latest attempt tracking, story-package gate, runway outcome classification, cartoon voice leak guard |
| `content_brain/platform/final_delivery_registry.py` | Guarded `try_update_final_delivery_registry()`; registry only updates when clips, assembly, topic, and video exist |
| `content_brain/platform/results_run_loader.py` | Import fix; approved vs attempt separation; run-scoped story package loading; story audit dataclass normalization |
| `content_brain/execution/runway_live_post_processor.py` | Fail-closed `evaluate_post_processing_eligibility()` on 0 clips / empty downloads |
| `content_brain/execution/runway_live_smoke_test.py` | Eligibility-gated post-processing; `record_latest_run_attempt()` on persist |
| `content_brain/audio/voice_identity_registry.py` | Topic/run scoped voice binding; blocks Whiskers/Sage reuse for non-cartoon topics |
| `content_brain/story/story_package.py` | Passes `run_id` + `topic` into voice registry |
| `ui/api/product_studio_service.py` | Creates isolated run context + story package on Create Video |
| `ui/api/schemas/product_studio.py` | Latest attempt + approved run DTO fields |
| `ui/web/src/api/productClient.ts` | Type updates for attempt/approved fields |
| `ui/web/src/pages/ResultsPage.tsx` | Separate **Latest Approved Video** and **Latest Attempt** panels |
| `project_brain/run_story_visual_1_test.py` | Registry update uses `force=True` with explicit guards |
| `project_brain/run_story_quality_1_test.py` | Same guarded registry update |
| `project_brain/validate_subject_drift_fail_closed.py` | **New** — 10 validation checks |
| `project_brain/PHASE_SUBJECT_DRIFT_REPAIR_1_REPORT.md` | This report |

---

## Fail-closed behavior

When Runway returns `clips_completed = 0`, empty `downloaded_file_paths`, or fails before the first valid clip:

1. Run status → **failed** (`latest_run_attempt.json`)
2. Message → **"Run failed before video generation — no final video created."**
3. **Post-processing skipped** (assembly, audio, branding, publish package)
4. **Asset Library not updated**
5. **`final_delivery_registry` unchanged** — previous approved video preserved

Post-processing is gated by `evaluate_post_processing_eligibility()` in both the smoke test runtime and the post-processor hook.

---

## Registry behavior

`try_update_final_delivery_registry()` requires (unless `force=True` for intentional test scripts):

- `approved=True`
- `clips_completed > 0`
- `assembly_status` in `{ASSEMBLED, COMPLETED}`
- `reality_audit_passed=True`
- Final video file exists on disk
- Run context topic matches supplied topic

Failed runs are tracked separately in `project_brain/runtime_state/latest_run_attempt.json` without overwriting approved delivery.

---

## Results UI behavior

The Results page now shows two distinct sections:

1. **Latest Approved Video** — from `final_delivery_registry` (previous cat run remains visible when valid)
2. **Latest Attempt** — from `latest_run_attempt.json` (park run: failed, 0 clips, explicit message)

Selected run history remains available but no longer mixes approved video from another run into the attempt view.

API fields added: `latest_run_attempt`, `latest_attempt_status`, `latest_attempt_message`, `latest_attempt_run_id`, `latest_attempt_topic`, `approved_run_id`.

---

## Run isolation (Create Video)

Each Create Video request now:

1. Runs Content Brain E2E for prompts
2. Calls `create_isolated_run_context(run_id, topic)` → story package, output folder, voice scope, visual memory path
3. Validates `require_story_package_for_run()` — **fails closed** if missing or cartoon character leak
4. Starts Runway only after isolation succeeds

No component falls back to a previous run’s story package, voice registry, or downloads unless the user explicitly opts into reuse (not implemented in this phase).

---

## Validation results

```text
python project_brain/validate_subject_drift_fail_closed.py
```

**ALL 10 CHECKS PASSED:**

1. New park topic creates isolated run context  
2. Zero clips → post-processing skipped  
3. Registry preserves previous approved video  
4. Latest attempt marked failed  
5. Results separate approved vs attempt  
6. Missing story package does not fall back to cat package  
7. Voice registry does not leak Whiskers/Sage for park topic  
8. Asset Library unchanged on failed finalize  
9. Results endpoint no `collect_valid_download_paths` NameError  
10. Story package topic matches run topic; zero downloads fail closed  

Real-project smoke:

```text
ProductStudioService.latest_results() — loads without NameError
```

---

## Notes / follow-ups

- Re-run Create Video for the park topic to populate `latest_run_attempt.json` on the live project (validation uses temp dirs; live attempt file updates on next Runway persist).
- Consider indexing failed runs in `outputs/runs/index.json` in a future phase (out of scope here).
- Test scripts (`run_story_visual_1_test.py`, `run_story_quality_1_test.py`) use `force=True` so intentional cat test deliveries can still lock registry when clips and assembly exist.
