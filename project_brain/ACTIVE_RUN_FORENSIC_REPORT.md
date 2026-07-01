# ACTIVE RUN FORENSIC REPORT

**Audit type:** Read-only — no modifications, no video generation, no credits  
**Audited at:** 2026-06-14  
**Sources:** `final_delivery_registry.json`, `canonical_run.json`, `outputs/runs/index.json`, `latest_run_attempt.json`, `run_contexts/`, `assets/asset_index.json`, `results_run_loader` (Results panel logic)

---

## Direct answers (1–8)

### 1. What is the newest run ever created?

| Field | Value |
|-------|--------|
| **run_id** | `cb_e2e_20260613_162423_dcde7693` |
| **topic** | Dog Training like pro |
| **created_at** | `2026-06-13T14:24:36.439800+00:00` (run context); publish/index completion `2026-06-13T15:03:18.346417+00:00` |
| **path** | `C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260613_170300_423_dcde7693` |

Newest by run-context `created_at` and by `outputs/runs/index.json` head entry. Older pending run contexts exist (boxing, trace test) but were created earlier the same day.

---

### 2. What is the newest successful Runway run?

| Field | Value |
|-------|--------|
| **run_id** | `cb_e2e_20260613_162423_dcde7693` |
| **topic** | Dog Training like pro |
| **created_at** | `2026-06-13T15:03:18.364680+00:00` (`latest_run_attempt.json` `updated_at`) |
| **path** | `C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260613_170300_423_dcde7693` |

Evidence: `latest_run_attempt.json` → `status: completed`, `run_ok: true`, `clips_completed: 2`, `downloaded_clip_count: 2`; checkpoint `publish_completed`; assembly `ASSEMBLED`.

---

### 3. What is the current canonical run?

| Field | Value |
|-------|--------|
| **run_id** | `cb_e2e_20260613_162423_dcde7693` |
| **topic** | Dog Training like pro |
| **created_at** | `2026-06-13T15:44:10.475636+00:00` (`canonical_run.json` `updated_at`) |
| **path** | `C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260613_170300_423_dcde7693` |

Source: `project_brain/runtime_state/canonical_run.json` (`source: runs_index_head`).

Note: same file also stores **validation metadata only** — `validation_topic: Sunrise coastal kayak guide for beginners` — not the active canonical topic.

---

### 4. What is the current approved run?

| Field | Value |
|-------|--------|
| **run_id** | `cb_e2e_20260613_162423_dcde7693` |
| **topic** | Dog Training like pro (resolved via `resolve_approved_delivery()` → canonical topic; registry JSON has no `topic` field) |
| **created_at** | `2026-06-13T17:26:53.362489+00:00` (`approved_at`) |
| **path** | `C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260613_170300_423_dcde7693\publish\FINAL_BRANDED_VIDEO_subtitle_fixed.mp4` |

Source: `final_delivery_registry.json` → `approved: true`, `delivery_reality_passed: true`.

---

### 5. What topic is shown in Results?

| Field | Value |
|-------|--------|
| **run_id** | `cb_e2e_20260613_162423_dcde7693` |
| **topic** | Dog Training like pro |
| **created_at** | Run index entry `2026-06-13T15:03:18.346417+00:00` |
| **path** | `C:\Users\kaman\Desktop\ModirAgentOS\outputs\runs\20260613_170300_423_dcde7693` |

Source: `load_run_results()` → `topic`, `canonical_run_id`, `selected_run_id` all align to dog run.

**Results delivery-truth panel (same run, different verdict):** `delivery_truth_status: FAIL` — audits `FINAL_BRANDED_VIDEO.mp4` (subtitle fail), not registry’s `subtitle_fixed` file. `approved_run_id` empty in Results payload.

---

### 6. What topic is shown in Registry?

| Field | Value |
|-------|--------|
| **run_id** | `cb_e2e_20260613_162423_dcde7693` |
| **topic** | Dog Training like pro |
| **created_at** | `2026-06-13T17:26:53.362500+00:00` (`updated_at`) |
| **path** | `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runtime_state\final_delivery_registry.json` |

---

### 7. What topic is shown in Asset Library?

| Field | Value |
|-------|--------|
| **run_id** | `cb_e2e_20260613_162423_dcde7693` |
| **topic** | Dog Training like pro |
| **created_at** | `2026-06-13T15:03:18.361662+00:00` (newest asset in `asset_index.json`) |
| **path** | `C:\Users\kaman\Desktop\ModirAgentOS\assets\videos\other\20260613_170318_dog_training_like_pro.mp4` |

Library root: `C:\Users\kaman\Desktop\ModirAgentOS\assets`

Head asset `source_video_path` points to pre-fix `FINAL_BRANDED_VIDEO.mp4`, not `FINAL_BRANDED_VIDEO_subtitle_fixed.mp4`.

---

### 8. What topic is shown in Latest Attempt?

| Field | Value |
|-------|--------|
| **run_id** | `cb_e2e_20260613_162423_dcde7693` |
| **topic** | Dog Training like pro |
| **created_at** | `2026-06-13T15:03:18.364680+00:00` (`updated_at`) |
| **path** | `C:\Users\kaman\Desktop\ModirAgentOS\project_brain\runtime_state\latest_run_attempt.json` |

Status: `completed` — “Run completed with downloadable clips.”

---

## Cross-system determination

### A. Are all systems pointing to the same run?

**YES**

All active surfaces use **`cb_e2e_20260613_162423_dcde7693`** / **Dog Training like pro**.

### B. If NO, list every conflicting run.

N/A — same run_id everywhere.

**Same-run sub-conflicts (not different run_ids):**

| Surface | Conflict |
|---------|----------|
| **Results delivery truth** | Audits `FINAL_BRANDED_VIDEO.mp4` → **FAIL**; does not use registry-approved `subtitle_fixed` MP4 |
| **Registry** | **PASS** / approved on `FINAL_BRANDED_VIDEO_subtitle_fixed.mp4` |
| **Asset Library** | Newest asset copied from original `FINAL_BRANDED_VIDEO.mp4` (pre subtitle-fix) |
| **Canonical metadata** | Stores validation-only topic “Sunrise coastal kayak guide for beginners” (not active run topic) |

**Inactive orphan run contexts on disk (not selected anywhere):**

| run_id | topic | status | path |
|--------|-------|--------|------|
| `cb_e2e_20260613_154308_8ed8ef38` | how to be legende in boxing | pending | `outputs/runs/20260613_154315_308_8ed8ef38` |
| `cb_e2e_20260613_153348_f05f58c6` | hhow to be legende in boxing | pending | `outputs/runs/20260613_153408_348_f05f58c6` |
| `cb_e2e_20260613_152852_780efb34` | how to be legende in boxing | pending | `outputs/runs/20260613_152911_852_780efb34` |
| `trace_test_run` | indoor herb garden tips | pending | `outputs/runs/20260613_154027_ace_test_run` |

---

### C. Which run is actually the newest run generated by the user?

**`cb_e2e_20260613_162423_dcde7693`** — **Dog Training like pro**

- Newest `run_contexts` entry by `created_at`
- Newest indexed Runway-complete run with downloaded clips
- Only run with `status: completed` in latest attempt lane among recent contexts

**Primary folder:** `outputs/runs/20260613_170300_423_dcde7693`  
**Upload-ready file (registry):** `publish/FINAL_BRANDED_VIDEO_subtitle_fixed.mp4`

---

## Summary table

| System | run_id | topic | Match? |
|--------|--------|-------|--------|
| Newest run ever | `cb_e2e_20260613_162423_dcde7693` | Dog Training like pro | ✓ |
| Newest successful Runway | same | same | ✓ |
| Canonical | same | same | ✓ |
| Approved (registry) | same | same | ✓ |
| Results (topic) | same | same | ✓ |
| Registry | same | same | ✓ |
| Asset Library (head) | same | same | ✓ |
| Latest Attempt | same | same | ✓ |

**Recommended next action (read-only finding):** Treat **`FINAL_BRANDED_VIDEO_subtitle_fixed.mp4`** as the authoritative deliverable. Results UI may still show delivery **FAIL** until `resolve_final_mp4_for_run()` / delivery-truth loader prefer the subtitle-fixed file over `FINAL_BRANDED_VIDEO.mp4`.
