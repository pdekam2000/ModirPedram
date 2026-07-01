# Kling Frame GUI Generate Failure — Forensic Report

**Phase:** FORENSIC — KLING FRAME GUI GENERATE FAILED AGAIN  
**Date:** 2026-06-18  
**Scope:** Investigation only — no code changes  
**Run folder root:** `outputs/kling_frame_to_video/`  
**Note:** No `outputs/kling_frame_to_video/latest` symlink exists; newest run selected by mtime.

---

## 1. Runs examined

| Run ID | Timestamp (UTC) | Operator | GUI symptom match |
|--------|-----------------|----------|-------------------|
| **`kling_ft_20260618T114614_e760da6e`** | 2026-06-18T11:46:14 | `pedram` | Latest GUI attempt (post partial approval fix) |
| **`kling_ft_20260618T112001_537db1f4`** | 2026-06-18T11:20:01 | `pop` | **Exact match** to reported failed response (`approved_by: pop`, `native_audio_status: failed`, `generate_clicked: false`) |

Both runs share the same underlying blocker: **no starter frame was available when live execution started.**

---

## 2. Primary run — `kling_ft_20260618T114614_e760da6e`

### 2.1 Artifact summary

**`metadata.json`**
```json
{
  "run_id": "kling_ft_20260618T114614_e760da6e",
  "topic": "moosh va gorbeh ba ham lambada miraghsand",
  "provider": "kling_3_0_pro_native_audio",
  "audio_strategy": "kling_native_audio",
  "native_audio_status": "planned",
  "generation_status": "prepared",
  "continuity_status": "stopped",
  "approved_by": "pedram",
  "output_ready": false,
  "clip_count": 2,
  "shot_mode": "kling_frame_to_video_native_audio"
}
```

**`generation_report.json`**
```json
{
  "version": "kling_frame_continuity_runtime_v1",
  "run_id": "kling_ft_20260618T114614_e760da6e",
  "status": "prepared",
  "precondition": "starter_frame_required",
  "precondition_message": "Starter frame required before live Generate.",
  "generation_mode": "kling_frame_to_video_native_audio",
  "clip_results": [],
  "continuity_status": "stopped",
  "chain_complete": false
}
```

**`continuity_chain.json`**
```json
{
  "continuity_status": "stopped",
  "stopped_at_clip": 1,
  "stop_reason": "starter_frame_required",
  "clips": [],
  "frames_extracted_count": 0,
  "frames_uploaded_count": 0
}
```

**`download_report.json`**
```json
{
  "run_id": "kling_ft_20260618T114614_e760da6e",
  "clip_count": 2,
  "status": "pending",
  "final_video_path": ""
}
```

**`approval.json`** (misleading — operator did approve)
```json
{
  "status": "failed",
  "approved_by": "pedram",
  "confirm_credit_spend": true,
  "approved_at": "2026-06-18T11:46:14.806387+00:00"
}
```

**`preflight.json`:** OK — frame plan present, 2 clips, `first_frame_source: user_upload`, **`first_frame_path: ""`** on clip 1.

**Missing artifacts (confirm live engine never ran):**
- No `clips/c1/` directory
- No `live_run_result.json`
- No `approval_checklist.json`
- No `starter_frame/frame_001.png` under this run folder
- No Runway live-engine screenshots

### 2.2 Failure stage

```
preflight ──OK──► approval gate ──OK──► starter frame ──BLOCK──► (never reached) frame upload / CDP / Generate
```

**Exact stage:** **starter frame** (pre-live-engine precondition)

**Failing function:** `run_kling_frame_continuity_chain()` in `content_brain/execution/kling_frame_continuity_runtime.py`

**Exact runtime branch (no exception, no traceback):**
- Clip 1 approved via `approve_generate`
- `upload_frame` / `starter_frame_path` is `None` (payload had no `first_frame_path`)
- Early return with `stop_reason: "starter_frame_required"`

**Exact error message (from artifacts):**
```
Starter frame required before live Generate.
```

**Continuity stop reason:**
```
starter_frame_required
```

### 2.3 Confirmation checklist

| Check | Result |
|-------|--------|
| Was Generate clicked? | **No** — `clip_results: []`, no `live_run_result.json`, no step `11_generate` |
| Was Runway queue entered? | **No** — live engine never invoked |
| Was any credit spent? | **No** — `credits_spent` not recorded; no Generate click |
| Did Chrome CDP connect? | **No** — no CDP step logs |
| Was Runway on Frames tab? | **No** — UI automation not started |
| Was starter frame uploaded? | **No** — no starter PNG in run folder; plan has empty `first_frame_path` |
| Was duration 15s? | **N/A** — duration slider step never reached |
| Was Audio ON? | **N/A** — audio toggle step never reached |

### 2.4 Backend traceback

**None.** Uvicorn logs show no `POST /product/create-video/generate` traceback for this window. Failure is a **clean early return**, not an uncaught exception.

### 2.5 Current API response (reproduced 2026-06-18)

Calling `ProductStudioService.create_video_generate()` with full approval and no `first_frame_path`:

```json
{
  "ok": true,
  "status": "prepared",
  "message": "Starter frame required before live Generate.",
  "approval_required": false,
  "generate_clicked": false,
  "credits_spent": false,
  "native_audio_status": "planned"
}
```

Backend no longer returns `status: failed` for this case after the approval-state fix. **GUI may still look “failed” if:**
- User hit the **earlier run** (`112001`, see §3), or
- UI reads **`approval.json` → `status: failed`** on Results, or
- Frontend bundle not refreshed (older handler only treated `awaiting_approval`, not `prepared`).

---

## 3. Secondary run — `kling_ft_20260618T112001_537db1f4` (matches original “failed” report)

This run matches the user-reported shape exactly:

**`metadata.json` excerpt:**
```json
{
  "run_id": "kling_ft_20260618T112001_537db1f4",
  "approved_by": "pop",
  "native_audio_status": "failed",
  "generation_status": "failed",
  "output_ready": false
}
```

**`generation_report.json` (entire file):**
```json
{
  "status": "failed",
  "run_id": "kling_ft_20260618T112001_537db1f4"
}
```

**`approval.json`:**
```json
{
  "status": "failed",
  "approved_by": "pop",
  "confirm_credit_spend": true
}
```

**Failure stage:** Same root cause (no starter frame), but **pre-fix** continuity runtime returned an empty `STATUS_FAILED` report instead of `prepared`. That produced **`native_audio_status: failed`** and GUI **`runStatus: failed`** via `!result.ok` / `native_audio_status === "failed"`.

**Failing code path (historical):** `kling_frame_continuity_runtime.py` — old branch returned `{"status": "failed"}` with empty `clip_results` when `starter_frame_path` was missing.

---

## 4. Pipeline gap (root cause)

Product Studio **does not generate or attach a starter frame** for GUI Generate:

1. `CreateVideoPage.tsx` sends `approve_generate`, `approved_by`, `confirm_credit_spend` — **does not send `first_frame_path`**
2. `run_kling_product_studio_generate()` reads `payload.get("first_frame_path")` → `None`
3. Frame plan clip 1 has `first_frame_source: "user_upload"` but **`first_frame_path: ""`**
4. Continuity chain stops at clip 1 before `run_kling_frame_to_video_live()`

Starter frame generation exists elsewhere (`kling_starter_frame_generator.py`, P4 live tool with `DEFAULT_STARTER_RUN_ID`) but is **not wired into Product Studio GUI generate flow**.

---

## 5. Contributing issues (not primary, but affect UX)

| Issue | Location | Effect |
|-------|----------|--------|
| `approval.json` written as `"status": "failed"` whenever `ok` is false | `kling_product_run.py` → `write_kling_output_package()` uses `"approved" if ok else "failed"` | Results / operators see “approval failed” even when operator fully approved |
| Empty `generation_report` on old path | Pre-fix continuity runtime | GUI got `status: failed`, `native_audio_status: failed` |
| No starter-frame UI step | `CreateVideoPage.tsx` | Operator cannot satisfy `user_upload` requirement from GUI |

---

## 6. Root cause (single sentence)

**Kling Frame-to-Video GUI Generate fails because Product Studio proceeds past operator approval without a starter/first frame image, so `run_kling_frame_continuity_chain()` exits at clip 1 with `stop_reason: starter_frame_required` before Runway/CDP/live Generate runs — no video is created and no credits are spent.**

---

## 7. Minimal fix recommendation (do not implement in this phase)

1. **Wire starter frame before live run** — auto-generate via `kling_starter_frame_generator` for the run_id, or require GUI upload and pass `first_frame_path` in generate payload.
2. **Block generate with clear UX** if starter frame missing (preflight warning + disable Generate), instead of silent post-approval stop.
3. **Fix `approval.json` semantics** — use `"approved"` when operator flags valid; use separate field for execution outcome (`prepared` / `failed`).
4. **Surface `precondition_message` in GUI** — show “Starter frame required…” as preparation, not generic “Generate failed”.

---

## 8. Status summary

| Field | Latest run (`114614`) | Earlier run (`112001`) |
|-------|----------------------|------------------------|
| **run_id** | `kling_ft_20260618T114614_e760da6e` | `kling_ft_20260618T112001_537db1f4` |
| **status** | `prepared` | `failed` |
| **native_audio_status** | `planned` | `failed` |
| **generate_clicked** | `false` | `false` |
| **credits_spent** | `false` | `false` |
| **Failing function** | `run_kling_frame_continuity_chain` | same (old empty-failed return) |
| **Exact message** | `Starter frame required before live Generate.` | implicit failed (empty report) |
| **Stack trace** | none | none |

**No video was created in either run because live Generate never started.**
