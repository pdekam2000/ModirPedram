# Subject Drift Forensic Report

Generated: 2026-06-13T10:15:00+00:00  
Phase: **SUBJECT-DRIFT-FORENSIC** (read-only)  
Scope: Why a new park-topic run still surfaces cartoon-cat story artifacts

---

## Executive answer

| Question | Answer |
|----------|--------|
| **Which subject should be active?** | The user’s **new Create Video topic** — recorded in the system as **`fantezy girl and man talking together in park`** (run `cb_e2e_20260613_120215_7eda6674`). The literal string **“boy and girl in park”** was **not found** anywhere on disk; the closest authoritative match is the topic above from `topic_authority_trace.json` (2026-06-13 10:02 UTC). |
| **Which subject is actually active in output/UI?** | **Cartoon cat / Whiskers–Sage story** — via `final_delivery_registry`, post-processing test runs, story packages, voice registry, and stale run index. |
| **Is old data leaking?** | **Yes — multiple layers.** Prompt generation and visual memory for the **new** run use the park topic, but **delivery, Results canon, story packages, audio characters, and reused runway video** still point at the cat pipeline. |

---

## 1. Current active run_id

| Source | run_id | Topic / notes |
|--------|--------|----------------|
| **Topic authority (new Create Video)** | `cb_e2e_20260613_120215_7eda6674` | `fantezy girl and man talking together in park` |
| **Runway live report (global)** | `cb_e2e_20260613_120215_7eda6674` | Same park topic; `ok: false`, `clips_completed: 0`, no downloads |
| **Final delivery registry (approved SSOT)** | `cb_sv1_20260613_095159_5fdbc1ce` | Whiskers/Sage crystal jungle (cartoon cat) |
| **Runs index (`outputs/runs/index.json`)** | `cb_e2e_20260611_225308_dc20bc1f` (listed first) | `Cute orange cartoon cat explorer` |
| **Latest post-processing run on disk** | `cb_sv1_20260613_095159_5fdbc1ce` | Cartoon cat story visual test |

**Finding:** There is **no single active run_id**. The **prompt/Runway path** targets the park e2e run; the **approved delivery path** targets the cartoon sv1 run; the **Results run history index** still lists the **June 11 cat Runway run** as newest indexed entry.

---

## 2. Story package topic

| Package file | run_id | topic |
|--------------|--------|-------|
| `cb_sv1_20260613_095159_5fdbc1ce.json` | cb_sv1… | `Whiskers and Sage — crystal jungle adventure` |
| `cb_sq1_20260613_091042_0717d140.json` | cb_sq1… | `Cute orange cartoon cat explorer` |
| *(none)* | `cb_e2e_20260613_120215_7eda6674` | **No story package exists** for the new park run |

**Finding:** Story packages were built only for **cartoon test/post-processing runs**, not for the new park e2e run. Any UI panel reading `story_packages/{run_id}.json` for the park run gets **empty / falls back**.

---

## 3. Visual memory subject

| Artifact | run_id key | subject |
|----------|------------|---------|
| `visual_memory/run_phase_i_live.json` | `phase_i_live` | **Fantezy Girl and Man Talking Together in Park** (updated 2026-06-13 10:02:36) |
| `visual_memory_report_phase_i_live.json` | `phase_i_live` | Same park subject, consistency PASS |
| Run-scoped report for `cb_e2e_20260613_120215_7eda6674` | — | **Missing** |
| Run-scoped report for `cb_sv1…` / cat runs | — | **Missing** |

**Finding:** Visual memory **was updated for the park topic** under the fixed key `phase_i_live`, not under the e2e run_id. Results loader resolves memory **per selected run_id** first — cat runs get **no** run-scoped memory file, so panels may appear empty or stale depending on selection.

---

## 4. Character / voice registry

**File:** `project_brain/runtime_state/voice_identity_registry.json`  
**Updated:** 2026-06-13T09:51:59 (during STORY-VISUAL-1 test, **before** park Create Video at 10:02)

| Character | speaking_style |
|-----------|----------------|
| Whiskers | fast_excited_cartoon |
| Sage | slow_caring_mentor |
| Narrator | warm storyteller |

**Finding:** Registry still encodes **cartoon cat/fox personas**, not park boy/girl characters. Cinematic multi-voice post-processing for sv1/sq1 runs **reuses these identities**.

---

## 5. Prompt builder subject

**Authoritative trace:** `project_brain/runtime_state/topic_authority_trace.json`

| Stage | Topic | run_id |
|-------|-------|--------|
| ui_request | fantezy girl and man talking together in park | — |
| prompt_builder | same | `cb_e2e_20260613_120215_7eda6674` |
| runway_runtime_start | same | — |

**Prompt outputs:** `project_brain/content_brain_test_results/cb_e2e_20260613_120215_7eda6674.runway_prompts.txt`  
- Starter + clip prompts reference **urban park**, **Fantezy Girl**, girl/man conversation — **correct for new topic**.  
- **No cat/Whiskers language** in generated Runway prompts.

**Finding:** Prompt builder is **NOT** leaking the cat subject. Drift happens **downstream** of prompt generation.

---

## 6. Automation queue job

| File | State |
|------|-------|
| `storage/content_brain/execution/queue/active_index.json` | `items: []` (empty, last updated 2026-06-04) |
| `storage/content_brain/execution/runtime/active_jobs.json` | `items: []` (empty) |

**Finding:** Automation queue is **not** carrying an old subject. Not a drift source.

---

## 7. Final delivery registry

**File:** `project_brain/runtime_state/final_delivery_registry.json`

| Field | Value |
|-------|-------|
| `latest_run_id` | `cb_sv1_20260613_095159_5fdbc1ce` |
| `latest_video` | `…/20260613_095159_f2d7ab07/publish/FINAL_BRANDED_VIDEO_v4.mp4` |
| `approved` | `true` |
| Topic (from run_summary) | **Whiskers and Sage — crystal jungle adventure** |

**Finding:** Registry was last updated by **`run_story_visual_1_test.py`** (cartoon post-processing), **overwriting** prior delivery. It does **not** reference the park e2e run. Any “Latest Approved Video” wired to registry shows **cat branded output**.

---

## 8. Results page subject

**Intended loader:** `content_brain/platform/results_run_loader.py` → `list_run_history()` → `outputs/runs/index.json`

| Behavior | Subject shown |
|----------|----------------|
| Default selected run (history[0]) | **Cute orange cartoon cat explorer** (`cb_e2e_20260611_225308_dc20bc1f`) |
| Approved video (registry match) | **Whiskers/Sage v4** when `run_id` = `cb_sv1…` |
| Park run `cb_e2e_20260613_120215_7eda6674` | **Not in run history index** — cannot be selected in dropdown |

**API note (observed):** `/product/results/latest` currently throws `NameError: collect_valid_download_paths is not defined` in `results_run_loader.py` (server log 2026-06-13). Results UI may error or show stale client state; when working, default canon is still **cat** from index.

**On-disk runs not indexed:** 4× June 13 test runs (sq1/sv1 cat) plus park e2e **never added** to `outputs/runs/index.json`.

---

## 9. Runway prompt subject (runtime)

| Artifact | Subject |
|----------|---------|
| `content_brain_test_results/latest.runway_prompts.txt` | Park / Fantezy Girl (`cb_e2e_20260613_120215_7eda6674`) |
| `runway_phase_i_3clip_last_report.json` | Park topic, same run_id; **failed run** (`ok: false`, 0 clips downloaded) |
| Reused assembly video in test runs | Copied from `outputs/runs/20260611_235927_308_dc20bc1f/final/FINAL_RUNWAY_PHASE_I_VIDEO.mp4` — **cartoon cat Runway output** |

**Finding:** **Prompts = park.** **Pixels in post-processed “final” videos = still cat** because test pipelines copy an old cat Runway assembly as `SOURCE_VIDEO_RUN`.

---

## Drift map (what leaks where)

```
User Create Video (park topic)
        │
        ├─► topic_authority_trace ──────────────► PARK ✓
        ├─► content_brain e2e / prompt builder ─► PARK ✓
        ├─► latest.runway_prompts.txt ───────────► PARK ✓
        ├─► visual_memory (phase_i_live) ────────► PARK ✓
        │
        ├─► runway execution ───────────────────► FAILED (no new video)
        │
        ▼
Post-processing / Results / Delivery layer
        │
        ├─► outputs/runs/index.json ─────────────► CAT (stale, Jun 11)
        ├─► final_delivery_registry ─────────────► CAT (cb_sv1, Jun 13 test)
        ├─► story_packages/* ────────────────────► CAT only
        ├─► voice_identity_registry ─────────────► Whiskers/Sage
        ├─► run_story_* tests SOURCE_VIDEO ──────► CAT runway MP4 reuse
        └─► Results “Latest Approved Video” ─────► CAT branded v4
```

---

## Components reusing old (cat) data

| Priority | Component | Mechanism |
|----------|-----------|-----------|
| **P0** | `final_delivery_registry.json` | Points approved delivery at sv1 cartoon run; updated by story visual test, not park e2e |
| **P0** | `run_story_visual_1_test.py` / `run_story_quality_1_test.py` | Hardcoded `SOURCE_VIDEO_RUN` = cat Runway folder; copies cat MP4 into new run folders |
| **P0** | `outputs/runs/index.json` | Never updated for park run or Jun 13 tests; Results defaults to cat e2e |
| **P1** | `project_brain/story_packages/` | Only cartoon packages; no package for park run_id |
| **P1** | `voice_identity_registry.json` | Whiskers/Sage locked from cartoon tests |
| **P1** | `resolve_approved_delivery()` | Registry run_id ≠ park run → approved cat video only when viewing sv1; other runs fall back to run folder video (still cat MP4 if copied) |
| **P2** | Global manifests (`runway_phase_i_*`) | Phase I paths/manifests from earlier cat era unless run-scoped match |
| **N/A** | Prompt builder / topic trace | **Not leaking** — park topic is correct |
| **N/A** | Automation queue | Empty |

---

## Topic string discrepancy

- User report: **“boy and girl in park”**
- System record: **“fantezy girl and man talking together in park”** (likely UI input / normalization; typo *fantezy* preserved)
- No file contains exact phrase `boy and girl in park`

Treat **park girl/man topic** as the intended new subject for this forensic.

---

## Conclusion

Subject drift is **real** but **split-brain**:

1. **Upstream (Content Brain → prompts → visual memory for `phase_i_live`)** reflects the **new park topic**.
2. **Downstream (delivery registry, Results index, story packages, voice registry, post-processing video source)** still reflects the **cartoon cat pipeline**, chiefly because:
   - Park Runway run **did not complete** (no new clips/downloads).
   - Post-processing tests **reused cat Runway video** and **rewrote** `final_delivery_registry`.
   - Run index **was not updated** for the new topic run.

**User-visible symptom:** New topic in Create Video, but “final” output / approved video / story audio / characters still feel like **Whiskers & Sage cartoon cat** — because those layers never switched to the park run and physically reuse cat media.

---

## Recommended fix direction (report only — not applied)

1. Register park e2e run in `outputs/runs/index.json` when Create Video completes (success or fail).
2. Stop post-processing tests from overwriting `final_delivery_registry` unless explicitly approved.
3. Build `story_package` + run-scoped visual memory for each e2e `run_id`, not only test harness runs.
4. Reset or topic-scope `voice_identity_registry` when topic changes.
5. Fix Results loader `collect_valid_download_paths` import so Results reflects run-scoped truth.
6. Do not copy `SOURCE_VIDEO_RUN` from unrelated Runway assemblies when validating a new topic.

---

*No files were modified during this forensic pass except this report.*
