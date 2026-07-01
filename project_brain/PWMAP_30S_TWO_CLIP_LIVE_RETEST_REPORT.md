# PWMAP 30s Two-Clip Live Retest Report

**Phase:** PWMAP-30S-TWO-CLIP-LIVE-RETEST  
**Date:** 2026-06-29  
**Verdict:** **FAIL** — duplicate stale download reproduced; guards failed closed correctly  
**Run ID:** `pwmap_20260629T101232_eda2c865`

---

## Executive summary

One controlled live 30s / 2-clip retest was executed with `free_credit_mode=true`, empty Specific Story Override (auto ideation), duplicate guards active, and no upload/publish bypass. Pre-live validations all passed. Free-credit-first rules were respected. Auto ideation produced a fresh non-repeated story. Use Frame continuity was applied for clip 2. **Clip 1 and clip 2 MP4 files are byte-identical** (same SHA-256), confirming root cause **B — stale download selection** at the pwmap/Runway layer persists. ModirAgentOS duplicate guard correctly marked clip 2 `duplicate_failed` and blocked approval.

**Do not proceed to PHASE PWMAP-40S-THREE-CLIP-CONTINUITY-RETEST** until distinct clip downloads are achieved at source.

---

## Part A — Pre-live validation

| Validator | Result |
|-----------|--------|
| `validate_channel_story_ideation_diversity` | **PASS** 19/19 |
| `validate_pwmap_30s_two_clip_duplicate_guard` | **PASS** 15/15 |
| `validate_results_run_truth_consistency` | **PASS** 19/19 |
| `validate_pwmap_30s_live_retest_safety` | **PASS** 15/15 |

### Fixes applied before live run

1. **`product_multiclip_orchestrator.py`** — dry-run path now returns `status: dry_run` without entering assembly/publish chain (was incorrectly surfacing `assembly_failed`).
2. **`pwmap_runway_agent_adapter.py`** — `_merge_credit_payload_fields()` propagates `free_credit_mode` and related flags from generate payload into pwmap preflight snapshot (second credit gate in `run_pwmap_agent` was blocking despite first gate passing).

---

## Part B — Credit safety preflight

| Field | Value |
|-------|-------|
| Provider | `runway` |
| Model | `Kling 3.0 Pro` |
| `credit_mode` | `free` |
| `free_credit_checked` | `true` |
| `paid_credit_risk` | `false` |
| `operator_paid_approval` | `false` |
| `estimated_credit_cost` | `2.0` (2 × 15s clips) |
| Execution allowed | **Yes** (`free_credit_mode=true`) |

**Free credits / free mode used:** Yes — `free_credit_mode=true` in payload; `credit_mode=free`; `may_spend_paid_credits=false`.  
**Paid credit risk during run:** No (explicit free mode).  
**Paid credits spent without approval:** No.

### Blocked attempt (pre-fix)

| Run ID | Issue |
|--------|-------|
| `pwmap_20260629T101108_445b8911` | `paid_credit_blocked` — `free_credit_mode` not propagated to `run_pwmap_agent` second gate. Fixed before successful live attempt. |

---

## Part C — Live test input

| Input | Value |
|-------|-------|
| Duration | 30s |
| Channel Topic / Niche | `dark fantasy analog horror stories` |
| Specific Story Override | **empty** |
| `free_credit_mode` | `true` |
| `live_retest` | `true` |
| YouTube upload | not requested / blocked by gates |

### Generated story (executed run)

Auto ideation ran inside `create_video_generate` preflight. Executed authoritative topic and prompts used a **salt-stained lighthouse stairwell** keeper-apprentice story — **not** prior repeated patterns (no dragon egg, no rooftop signal).

**Preflight ideation title (first pass, forensic capture):**  
`The Waterlogged Vhs Case at Flooded Subway — Variant 6d6dbe`

**Executed story (job.json / authoritative_topic):**  
Lighthouse stairwell / storm-damaged logbook / repeating telegraph signal — distinct prompts for clips 1 and 2.

**Specific Story Override empty:** Confirmed (`story_override_active: false`).

---

## Part D — Runtime behavior

| Check | Result |
|-------|--------|
| `requested_clip_count` | **2** |
| `clip_3` | **not applicable** (no `clip_3.mp4`) |
| `execution_mode` | `use_frame_chain` |
| Clip 1 generated/downloaded | **Yes** |
| Clip 2 Use Frame from clip 1 | **Yes** (subprocess log) |
| Clip 2 generated after Use Frame | **Yes** |
| Clip 1 prompt exists | **Yes** |
| Clip 2 prompt exists | **Yes** |
| Prompts different but continuous | **Yes** |
| Clip 1 MP4 exists | **Yes** |
| Clip 2 MP4 exists | **Yes** |
| SHA-256 differ | **NO — FAIL** |
| `generation_success` | subprocess exit 0; adapter `ok: false` after guard |
| `download_success` | both files on disk; clip 2 `valid: false` |

### Prompt hashes

| Clip | SHA-256 (prompt text) |
|------|------------------------|
| Clip 1 | `d0455017ada84d42f18e8bc593d643d7cd7e63b69e23ae4144a4c3ca6d5f6fba` |
| Clip 2 | `98429b25314e8fedca1c9ccbcb129183992fe14b883a0fb272e7340ecc424d42` |

### MP4 SHA-256

| Clip | SHA-256 | Source path |
|------|---------|-------------|
| Clip 1 | `cb01be2c3550cc0065f3e808586962ba5c02cbe236c7c32b71f56623e6554b35` | `clip_001_20260629_122544.mp4` |
| Clip 2 | `cb01be2c3550cc0065f3e808586962ba5c02cbe236c7c32b71f56623e6554b35` | `clip_002_20260629_123955.mp4` |

**Hashes differ:** **NO** — identical bytes despite different download filenames/timestamps.

### Use Frame evidence

From `subprocess_stdout.log`:

```
CLIP 2/2
[step] Use frame from previous clip (last frame)...
[OK] 'Use frame' is visible under previous clip.
[step] Seeking previous clip to second 14 (last frame)...
[OK] Use frame clicked (last frame).
[OK] Downloaded: ...\clip_002_20260629_123955.mp4
```

`use_frame_evidence: true` in forensic JSON.  
`use_frame_gate` for clip 2: `pass`, `used_frame_from_previous: true`, `log_used_frame: true`.

### Download freshness / duplicate guard

| Clip | Freshness | Duplicate gate |
|------|-----------|----------------|
| 1 | `fresh` / pass | pass |
| 2 | `ambiguous_stale_output` / `duplicate_hash` | **`duplicate_failed`** |

**Error (clip 2):**  
`Downloaded clip is byte-identical to a previous clip; possible stale output/download selection.`

**Adapter final status:** `duplicate_failed`  
**Orchestrator status:** `partial` (`ok: true` at orchestrator layer; normalized adapter `ok: false`).

---

## Part E — Results truth

| Field | Value |
|-------|-------|
| Duration (plan) | 30s |
| Requested clips (plan) | 2 |
| Downloaded clips (disk) | 2 |
| Clip 3 | not applicable |
| Clip 1 hash ≠ Clip 2 hash | **NO** |
| Candidate video | present (`video.mp4` / clip_1 partial) |
| Approved | **false** |
| `video_display_label` | `Unapproved Candidate Video` |
| `duplicate_chain_failed` | **true** |
| Clip 2 status | `duplicate_failed` |
| Delivery Truth | **FAIL** (subtitles check among failures) |
| YouTube upload executed | **No** (`youtube_upload_status` empty) |
| Safety gate bypass | **None** |

### Known Results metadata gaps (non-blocking for this verdict)

- `expected_clip_count` resolves to `1` in merged Results for this run (should be 2 for 30s) — duration metadata not fully persisted on run folder.
- `youtube_upload_allowed` still `true` in `run_truth` despite `duplicate_chain_failed` — upload was not attempted; recommend tightening upload gate on duplicate failure in a follow-up.

---

## Part F — Success criteria checklist

| Criterion | Met? |
|-----------|------|
| All validation passes | **Yes** |
| Free-credit-first respected | **Yes** |
| Auto ideation fresh non-repeated story | **Yes** |
| 30s maps to exactly 2 clips | **Yes** |
| `clip_3` N/A | **Yes** |
| Clip 1 and clip 2 hashes differ | **NO** |
| Use Frame evidence exists | **Yes** |
| Results truthful (unapproved on duplicate) | **Yes** |
| No upload/publish bypass | **Yes** |
| No paid credits without approval | **Yes** |

**Overall phase verdict:** **FAIL**

---

## Artifacts

| Artifact | Path |
|----------|------|
| Run directory | `outputs/pwmap_agent_runs/pwmap_20260629T101232_eda2c865/` |
| Forensic JSON | `.../live_retest_forensic.json` |
| Subprocess log | `.../subprocess_stdout.log` |
| Normalized result | `.../normalized_result.json` |
| Job / prompts | `.../job.json` |
| Live runner log | `project_brain/live_retest_run.log` |

---

## Confirmations

- Duplicate/stale download guards **active and fail-closed**
- No manual publish or YouTube upload bypass
- No paid credit execution without operator approval
- Free-credit mode used for the successful live attempt
- Root cause **B (stale download selection)** reproduced at pwmap `runway_downloads` **before** ModirAgentOS copy

---

## Next recommended phase

**PHASE PWMAP-STALE-DOWNLOAD-SELECTION-FIX** (or equivalent)

Focus: ensure pwmap `runway_agent.py` download step selects the **newly generated** clip asset for clip 2 (not a cached/stale file), e.g.:

- wait for new DOM/download token after clip 2 generation completes
- verify download URL or file mtime changes between clips
- reject download if byte hash matches prior clip **at pwmap layer** before returning `last_result.json`

Only after a live 30s retest shows **distinct clip SHA-256** with Use Frame continuity:

→ **PHASE PWMAP-40S-THREE-CLIP-CONTINUITY-RETEST**
