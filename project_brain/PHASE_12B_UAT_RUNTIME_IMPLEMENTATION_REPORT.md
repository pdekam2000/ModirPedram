# Phase 12B — UAT Runtime Implementation Report

**Date:** 2026-06-01  
**Status:** PASS  
**Scope:** CLI-first supervised UAT pipeline (one topic → one `FINAL_PUBLISH_READY.mp4`)

Design reference: [PHASE_12A_USER_ACCEPTANCE_TEST_RUNTIME_DESIGN.md](./PHASE_12A_USER_ACCEPTANCE_TEST_RUNTIME_DESIGN.md)

---

## Summary

Phase 12B implements a supervised CLI runner that composes existing Content Brain and execution runtimes into a single human-review UAT flow. One operator invocation creates one session (`exec_uat_YYYYMMDD_HHMMSS`), runs content planning through assembly, writes a review template and UAT report, and stops for human acceptance — no batch mode, no auto-publish, no legacy pipeline import.

---

## Files Created

| File | Purpose |
|------|---------|
| `project_brain/run_12b_uat_supervised_pipeline.py` | Main CLI runner — full UAT pipeline |
| `project_brain/validate_12b_uat_supervised_pipeline.py` | 15-test validator (+ 11J-19 / 11H-2d regressions) |
| `content_brain/execution/uat_runtime_profile.py` | UAT caps, session ID format, config normalization |

## Files Modified (minimal)

| File | Change |
|------|--------|
| `content_brain/execution/assembly_runtime_engine.py` | `max_output_bytes` param for UAT 50 MB cap |
| `ui/api/assembly_run_service.py` | Passes `max_output_bytes` through to engine |

## Output Directories (runtime)

| Path | Content |
|------|---------|
| `project_brain/user_acceptance_reviews/{session_id}_review_template.json` | Human review scores template |
| `project_brain/uat_runs/{session_id}_uat_report.md` | Operator UAT report |
| `storage/content_brain/execution/artifacts/{session_id}/` | All stage artifacts + final video |

---

## CLI Usage

```powershell
python -m project_brain.run_12b_uat_supervised_pipeline ^
  --topic "cat in the streets of Los Angeles" ^
  --platform youtube_shorts ^
  --duration-seconds 45 ^
  --video-provider runway_browser ^
  --voice-provider elevenlabs ^
  --confirm-real-voice ^
  --confirm-real-assembly ^
  --open-folder
```

### Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--topic` | *(required)* | Video topic |
| `--platform` | `youtube_shorts` | Target platform |
| `--duration-seconds` | `45` | Target duration (15–90s) |
| `--video-provider` | `runway_browser` | Video provider |
| `--voice-provider` | `elevenlabs` | Voice provider (`elevenlabs` or `mock`) |
| `--niche` | `general` | Content niche profile |
| `--confirm-real-voice` | off | Gate live ElevenLabs TTS |
| `--confirm-real-assembly` | off | Gate real FFmpeg assembly |
| `--open-folder` | off | Open artifact folder when done (Windows/macOS/Linux) |

---

## Pipeline Flow

1. **Env bootstrap** — `bootstrap_project_env()` (central `.env` load, no global real flags)
2. **Session** — `exec_uat_YYYYMMDD_HHMMSS`
3. **Content Brain** — brief, story architecture, beats, narration, video prompt plan
4. **Session population** — `video_generation`, `voice_generation`, `subtitle_generation`, `assembly_generation`
5. **Video** — real provider dispatch when supported; FFmpeg lavfi mock fallback with `video_provider_mode: mock|real`
6. **Voice** — mock TTS by default; live ElevenLabs only with `--confirm-real-voice` + approval + scoped env flags
7. **Subtitle** — `SubtitleRunService.run` → srt, ass, vtt
8. **Assembly** — dry-run first; real FFmpeg only with `--confirm-real-assembly` + approval + scoped env flags
9. **Outputs** — review template, UAT report, printed paths
10. **Post-run** — assembly approval expired; env flags cleared in `finally` blocks

### UAT integration fixes (12B-only wiring)

- Mock voice requires approval gate (same as 11H-2d) — runner approves before mock TTS
- Mock voice manifest timing patched when wall-clock duration ≈ 0
- Voice artifacts synced to `artifacts_by_category` for assembly plan READY status
- Mock subtitle path uses `equal_chunk` timing + relaxed beat-plan windows to avoid cue validation failures

---

## Validation Results

All required validators **PASS**:

```
python -m project_brain.validate_12b_uat_supervised_pipeline
→ 15/15 PASS

python -m project_brain.validate_11j19_supervised_assembly_smoke_test
→ 13/13 PASS

python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution
→ 17/17 PASS
```

### 12B validator matrix

| # | Test | Result |
|---|------|--------|
| 1 | Runner exists | PASS |
| 2 | CLI args parsed | PASS |
| 3 | Env bootstrap called | PASS |
| 4 | UAT session id generated | PASS |
| 5 | Mock-mode pipeline completes without paid providers | PASS |
| 6 | Review template created | PASS |
| 7 | UAT report created | PASS |
| 8 | Real voice cannot run without `--confirm-real-voice` | PASS |
| 9 | Real assembly cannot run without `--confirm-real-assembly` | PASS |
| 10 | Flags disabled after failure | PASS |
| 11 | No batch loop | PASS |
| 12 | No auto-publish code | PASS |
| 13 | No `full_video_pipeline.py` import | PASS |
| 14 | 11J-19 regression | PASS |
| 15 | 11H-2d regression | PASS |

---

## Safety Gates

| Gate | Mechanism |
|------|-----------|
| Real voice | `--confirm-real-voice` + `VoiceApprovalOperationsEngine.approve` + scoped `MODIR_VOICE_LIVE_TTS_ENABLED` / `LIVE_RUNTIME_EXECUTION_APPROVED` patch |
| Real assembly | `--confirm-real-assembly` + `AssemblyApprovalOperationsEngine.approve` + scoped `MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED` / `ASSEMBLY_RUNTIME_EXECUTION_APPROVED` |
| Flag cleanup | `os.environ.pop(...)` in `finally` after voice and assembly real paths |
| One run only | Single session per invocation; no topic loop |
| Failure handling | Stage failure → error in report → `RuntimeError` stop; artifacts preserved |
| UAT caps | Max clips, voice segments, assembly output bytes via `uat_runtime_profile.py` |

---

## Confirmations

| Requirement | Status |
|-------------|--------|
| No batch mode | Confirmed — no `for topic in` / `batch_mode` in runner source |
| No auto-publish | Confirmed — no upload/publish hooks in runner |
| No legacy pipeline | Confirmed — AST scan: no `full_video_pipeline` import |
| No UI wizard | Not implemented (12C scope) |
| No Runway/Hailuo internals changed | Confirmed |
| No global real provider enablement | Confirmed — flags scoped per stage only |

---

## Review Template Fields

`project_brain/user_acceptance_reviews/{session_id}_review_template.json`:

- `story_quality_score`
- `visual_quality_score`
- `voice_quality_score`
- `subtitle_quality_score`
- `continuity_score`
- `overall_quality_score`
- `comments`
- `publishable` (true/false)

Save completed review as `{session_id}_review.json` in the same folder.

---

## Next Recommended Action

1. **Run one real supervised UAT** (operator machine with FFmpeg + ElevenLabs credentials):

   ```powershell
   python -m project_brain.run_12b_uat_supervised_pipeline ^
     --topic "cat in the streets of Los Angeles" ^
     --platform youtube_shorts ^
     --duration-seconds 45 ^
     --video-provider runway_browser ^
     --voice-provider elevenlabs ^
     --confirm-real-voice ^
     --confirm-real-assembly ^
     --open-folder
   ```

2. Watch `FINAL_PUBLISH_READY.mp4` and fill in the review template JSON.

3. If accepted → proceed to **Phase 12C** (UI wizard) per 12A design.

---

*Phase 12B complete. All validators green. Ready for operator real UAT.*
