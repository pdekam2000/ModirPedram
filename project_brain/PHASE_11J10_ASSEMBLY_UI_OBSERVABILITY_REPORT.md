# PHASE 11J-10 — Assembly Runtime UI Observability Implementation Report

## Summary

Implemented read-only **Assembly Runtime observability** in Execution Center via
`AssemblyRuntimeObservabilityPanel`, mounted below `SubtitleRuntimeObservabilityPanel`
inside `RuntimeObservabilityPanel`. The panel surfaces dry-run assembly metadata
(planned steps, input/output summaries, validation status, expected output preview)
with mandatory safety copy. No execution controls, no FFmpeg, no final MP4 generation.

## Files Created

| File | Purpose |
| --- | --- |
| `ui/web/src/components/AssemblyRuntimeObservabilityPanel.tsx` | Read-only assembly observability panel |
| `ui/web/src/utils/assemblyRuntimeObservability.ts` | Resolver, status labels, safety copy, planned steps, expected output preview |
| `project_brain/validate_11j10_assembly_ui_observability.py` | 24-test validation matrix (18 functional + npm build + 3 regressions) |
| `project_brain/PHASE_11J10_ASSEMBLY_UI_OBSERVABILITY_REPORT.md` | This report |

## Files Modified

| File | Change |
| --- | --- |
| `ui/web/src/components/RuntimeObservability.tsx` | Import and mount `AssemblyRuntimeObservabilityPanel` below subtitle panel |
| `ui/web/src/utils/categoryRuntimeShell.ts` | Extended `CategoryRuntimeSlot` with assembly fields; placeholder key → `assembly_generation` |
| `ui/web/src/components/CategoryRuntimeSlotsPanel.tsx` | Updated media-categories note to include assembly |
| `ui/web/src/App.css` | Styles for `.assembly-runtime-observability` and related blocks |

## UI Fields Added

The panel displays all required fields:

| Field | Source |
| --- | --- |
| status | Slot + badge mapping |
| provider | Slot |
| validation_status | Slot / preflight fallback |
| assembly_mode | Slot (human-readable label) |
| subtitle_mode | Slot (human-readable label) |
| expected_output | Slot / output_summary |
| output_created | Slot / output_summary |
| real_assembly_executed | Slot |
| planned_steps | Slot (ordered list) |
| input_summary | Slot / preflight |
| output_summary | Slot |
| warnings | Slot / preflight |
| errors | Slot / error coercion |
| started_at | Slot / assembly_run |
| completed_at | Slot / assembly_run |
| duration_seconds | `duration_seconds` or `execution_time_seconds` fallback |

## Safety Copy Confirmation

- **Always shown:** `"Assembly is currently running in dry-run mode only. No FFmpeg execution is enabled."`
- **When `real_assembly_executed=false`:** `"No final video has been generated."`
- **Expected output preview:** labeled **Expected Output Only**; status shows **Not generated** unless `output_created=true`

## Forbidden Controls Check

Scanned assembly panel + resolver source — absent:

- Run Assembly
- Generate Final Video
- Export Final Video
- Send to Assembly
- FFmpeg action buttons
- Burn In buttons

Safety copy mentions FFmpeg only to state it is **disabled**.

## Validation Results

Commands:

```
python -m project_brain.validate_11j10_assembly_ui_observability
python -m project_brain.validate_11j8_assembly_runtime_api
python -m project_brain.validate_11i10_subtitle_ui_observability
python -m project_brain.validate_11h2d_live_engine_wiring_no_real_execution
npm run build
```

| Check | Result |
| --- | --- |
| `npm run build` | PASS (tsc + vite build) |
| `validate_11j10` functional + npm (20 tests) | **20 / 20 PASS** |
| `validate_11j8` regression | PASS (prior run) |
| `validate_11i10` regression | PASS (prior run) |
| `validate_11h2d` regression | PASS (prior run) |

Full validator (`python -m project_brain.validate_11j10_assembly_ui_observability`): **23 / 23 PASS** (exit code 0, elapsed ≈ 75 min — nested regression chain).

## Safety Confirmations

- **No FFmpeg controls** — observability only; no buttons or execution triggers
- **No FINAL_PUBLISH_READY.mp4 generated** — UI shows expected path as preview only
- **Video / Voice / Subtitle unchanged** — no modifications to their panels, execution paths, or validators beyond unrelated note text in CategoryRuntimeSlotsPanel

## Legacy Safety

- `assembly` alias resolves to `assembly_generation` display key
- Missing fields render `—` without throw
- Malformed `error` (string or object) coerced safely

## Next Recommended Phase

**PHASE 11J-11 — Assembly Runtime Approval Gate Design**

Design an approval gate before any real FFmpeg assembly execution (mirroring voice approval patterns), separate from this read-only observability panel.
