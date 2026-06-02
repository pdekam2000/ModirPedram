# PHASE E2E-40S — Test Memory Cleanup Report

**Date:** 2026-06-02  
**Scope:** Remove pre-isolation E2E planning-probe row from production uniqueness memory only.

---

## Summary

| Item | Result |
|------|--------|
| Cleanup script | `project_brain/cleanup_e2e_test_uniqueness_record.py` |
| Validator | `project_brain/validate_e2e_test_uniqueness_cleanup.py` — **all checks PASS** |
| Production cleanup executed | **Yes** |
| Records removed | **1** (`uniq_e792a4abf5`, Girl in Rain, 18:16:43) |
| Records remaining | **0** |
| Backup | `storage/content_brain/memory/uniqueness/backups/content_history.backup_20260602_185906.json` |
| Post-cleanup brief (same topic as failed UAT) | **PROCEED**, uniqueness 100.0, 5 clips @ 40s |

Production thresholds, `UniquenessEngine`, and full-file deletion were **not** changed.

---

## Problem (recap)

One test-only row in `storage/content_brain/memory/uniqueness/content_history.json` (from E2E planning probe before memory isolation) caused structural collision for rain/girl topics:

- `beat_sequence_fingerprint` = 1.0  
- `hook_fingerprint` / `twist_type_collision` failures  
- `uniqueness_score` = 0.0 → `story_quality` = REJECT  

See: `PHASE_E2E_40S_REJECT_TRACE_2_REPORT.md`

---

## Cleanup script behavior

**Command:**

```powershell
python project_brain/cleanup_e2e_test_uniqueness_record.py
```

**Dry-run:**

```powershell
python project_brain/cleanup_e2e_test_uniqueness_record.py --dry-run
```

**Matching rule (conservative):** topic `Girl in Rain` **and** at least one corroborating signal:

- `record_id` = `uniq_e792a4abf5`, or  
- `created_at` prefix `2026-06-02 18:16:`, or  
- E2E metadata on record (`source` / `e2e_planning_probe`), or  
- known probe hook + beat fingerprints at that timestamp  

**Does not remove:** other topics, or `Girl in Rain` rows without probe signals (validator fixture `uniq_other_girl_rain` preserved in tests).

**Steps:**

1. Load `content_history.json`  
2. Timestamped backup under `storage/content_brain/memory/uniqueness/backups/`  
3. Remove matching records only  
4. Write valid JSON with remaining `records` array (may be empty)  
5. Exit 0 with message if no match  

---

## Production cleanup run output

```
[cleanup] memory_path=...\storage\content_brain\memory\uniqueness\content_history.json
[cleanup] dry_run=False
[cleanup] original_count=1
[cleanup] removed_count=1
[cleanup] remaining_count=0
[cleanup] backup_path=...\backups\content_history.backup_20260602_185906.json
[cleanup] removed record_id=uniq_e792a4abf5 topic='Girl in Rain' created_at=2026-06-02 18:16:43
[cleanup] Cleanup complete.
```

**After state** (`content_history.json`):

```json
{
  "records": []
}
```

---

## Validation

```powershell
python project_brain/validate_e2e_test_uniqueness_cleanup.py
```

| Check | Status |
|-------|--------|
| Backup created on removal | PASS |
| Only target record removed | PASS |
| Unrelated records preserved (fixture) | PASS |
| Safe when record missing | PASS |
| JSON remains valid | PASS |
| Dry-run leaves file unchanged | PASS |

---

## Post-cleanup Content Brain check

Topic: `lonely girl running through neon rain street`, 40s, `runway_browser`, evaluate-only (no record):

| Field | Before cleanup | After cleanup |
|-------|----------------|---------------|
| decision | REJECT | **PROCEED** |
| production_ready | false | **true** |
| uniqueness_passed | false | **true** |
| uniqueness_score | 0.0 | **100.0** |
| max_similarity | 1.0 | **0.0** |
| planned clips | 5 | **5** |

This confirms the blocker was the test memory row, not the new topic string.

---

## Full 40s UAT (operator run)

Cleanup does **not** replace a supervised Runway/ElevenLabs/assembly run. Use Runtime Studio or CLI with confirmations:

```powershell
$env:UAT_E2E_VALIDATION_FULL_DURATION = "1"
python project_brain/run_12b_uat_supervised_pipeline.py `
  --topic "lonely girl running through neon rain street" `
  --duration-seconds 40 `
  --video-provider runway_browser `
  --voice-provider elevenlabs `
  --confirm-real-voice `
  --confirm-real-video `
  --confirm-real-assembly
```

**UI equivalent:** topic as above, duration **40**, Runway Browser, video approval enabled, ElevenLabs + real assembly confirmed.

**Prerequisites:** API running (`python -m ui.api.main`), Chrome CDP for Runway, ElevenLabs env, operator at browser for generation.

**Note:** `run_e2e_40s_validation.py` still defaults topic to `Girl in Rain` in `TEST_CONFIG`; for this validation use the topic above explicitly.

### Post-cleanup UAT started (2026-06-02)

CLI run launched with the command above. Early session:

| Field | Value |
|-------|--------|
| session_id | `exec_uat_20260602_190032` |
| topic | lonely girl running through neon rain street |
| content_brain decision | **PROCEED** |
| story_quality.decision | **PROCEED** |
| execution_readiness | **READY_WITH_WARNINGS** |
| state (in progress) | RUNNING → queued for video |

Monitor terminal / Runtime Studio for Runway + ElevenLabs + assembly completion.

---

## Related fixes

- Probe isolation (no future pollution): `PHASE_E2E_40S_UNIQUENESS_MEMORY_ISOLATION_FIX_REPORT.md`  
- Reject traces: `PHASE_E2E_40S_REJECT_ROOT_CAUSE_AUDIT.md`, `PHASE_E2E_40S_REJECT_TRACE_2_REPORT.md`

---

## Restore from backup (if needed)

```powershell
Copy-Item `
  storage\content_brain\memory\uniqueness\backups\content_history.backup_20260602_185906.json `
  storage\content_brain\memory\uniqueness\content_history.json
```

Only restore if you intentionally need the removed test row back.
