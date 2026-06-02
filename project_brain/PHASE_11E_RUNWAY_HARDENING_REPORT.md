# Phase 11E — Runway Hardening (Consolidated Report)

**Status:** CLOSED (Phase 11E-g)  
**Date:** 2026-05-28  
**Design:** `PHASE_11E_RUNWAY_HARDENING_DESIGN_REPORT.md`  
**Final validation:** `validate_11e_matrix` (orchestrates all slice validators + regressions)

---

## Phase Summary

Phase **11E** hardens Runway **API** and **browser** video generation paths without changing the active default provider (`runway_browser`), without implementing image-to-video, and without automatic failover execution. Work spans preflight/config, bounded execution, structured errors, normalized artifacts, runtime cancel wiring, and failover **advisory** metadata.

---

## Slice Summary (11E-a → 11E-g)

| Slice | Focus | Validation | Result |
|-------|--------|------------|--------|
| **11E-a** | Config unification, Runway preflight, error taxonomy | `validate_11e_a_runway_preflight` | 25/25 PASS |
| **11E-b** | API mode hardening (polling, cancel, downloads) | `validate_11e_b_runway_api_hardening` | 24/24 PASS |
| **11E-c** | Browser mode hardening (bounded waits, no infinite sleep) | `validate_11e_c_runway_browser_hardening` | 18/18 PASS |
| **11E-d** | Shared artifact normalization & continuity | `validate_11e_d_runway_artifacts` | 20/20 PASS |
| **11E-e** | Runtime `cancel_check` wiring | `validate_11e_e_runtime_cancel_wiring` | 26/26 PASS |
| **11E-f** | Failover readiness advisory (11C/11D) | `validate_11e_f_runway_failover_advisory` | 26/26 PASS |
| **11E-g** | Final matrix + handoff | `validate_11e_matrix` | **38/38 PASS** |

---

## Files Created (11E program)

| File | Slice |
|------|-------|
| `content_brain/execution/runway_config.py` | 11E-a |
| `content_brain/execution/runway_preflight.py` | 11E-a |
| `providers/runway_error_classifier.py` | 11E-a |
| `providers/runway_api_errors.py` | 11E-b |
| `providers/runway_browser_support.py` | 11E-c |
| `providers/runway_artifact_utils.py` | 11E-d |
| `content_brain/execution/provider_cancel_wiring.py` | 11E-e |
| `content_brain/execution/runway_failover_advisory.py` | 11E-f |
| `project_brain/validate_11e_a_runway_preflight.py` … `validate_11e_matrix.py` | All |
| `project_brain/PHASE_11E-a_IMPLEMENTATION_REPORT.md` … `PHASE_11E-g_IMPLEMENTATION_REPORT.md` | All |
| `project_brain/PHASE_11E_RUNWAY_HARDENING_REPORT.md` | 11E-g |

---

## Files Modified (11E program)

| File | Changes |
|------|---------|
| `content_brain/execution/failure_taxonomy.py` | Runway-related taxonomy codes |
| `content_brain/execution/provider_preflight_validator.py` | Runway preflight hook |
| `providers/runway_video_provider.py` | API hardening, artifacts, cancel |
| `providers/runway_browser_provider.py` | Browser cancel checkpoints |
| `providers/runway_download_provider.py` | Normalized downloads |
| `orchestrators/runway_browser_orchestrator.py` | Bounded waits, partial artifacts, **removed infinite sleep** |
| `core/video_provider_router.py` | Optional `cancel_check` forwarding |
| `content_brain/execution/provider_runtime_engine.py` | Cancel handling, advisory attachment |

**Unchanged by design:** UI, active default provider, automatic failover execution, I2V runtime.

---

## Config & Preflight (11E-a)

- `RunwayConfigResolver` unifies registry, mode catalog, env, and active provider.
- `RunwayPreflightEngine` validates capability, credentials, disabled state before dispatch.
- `runway_error_classifier` maps Runway errors → failure taxonomy (`PROVIDER_TIMEOUT`, `ARTIFACT_TOO_SMALL`, etc.).
- Active default remains **`runway_browser`**.

---

## API Hardening (11E-b)

- Bounded task polling with configurable intervals.
- Cooperative `cancel_check` at clip and poll boundaries.
- Structured `RunwayProviderError` / `RunwayCancelledError`.
- Minimum download size gate (100 KB); files preserved on failure.
- Lazy `requests` import for test environments.

---

## Browser Hardening (11E-c)

- **Removed `time.sleep(999999)`** infinite worker block.
- Bounded generation waits (`RUNWAY_BROWSER_MAX_WAIT_SECONDS`, default 900s).
- Cancel checkpoints across launch, prompt, wait, download.
- Structured errors via `runway_browser_support`.
- Cleanup in `finally` blocks.

---

## Artifact Continuity (11E-d)

- `runway_artifact_utils.py` — shared normalized records for API + browser.
- Standard fields: `file_path`, `provider_id`, `mode`, `size_bytes`, `sha256`, `validation_status`, `partial`.
- Partial bundles on cancel/failure; **artifacts never deleted** on validation failure.
- Compatible with 10J-e `ArtifactValidationEngine` and 10K operations metadata.

---

## Runtime Cancel Wiring (11E-e)

- `ProviderRuntimeEngine` builds live `cancel_check` from `operations_control.cancel_requested`.
- `VideoProviderRouter` forwards to Runway API/browser via signature-safe helper.
- `RunwayCancelledError` → session **CANCELLED** (not FAILED), `OPERATIONS_CANCELLED` failure code.
- Partial paths canonicalized under session artifact root.

---

## Failover Advisory (11E-f)

- `operations.failover_advisory` attached on terminal Runway FAILED/CANCELLED paths.
- Uses **11C** `ProviderFailoverPlanner` and **11D** `ProviderSelectionEngine` (metadata only).
- Operator cancel → `failover_recommended=false`.
- Provider failure → may suggest next candidate with cost/capability warnings.
- **`advisory_only: true`** — no dispatch, retry, or requeue.

---

## Validation Results

### Individual validators

```bash
py -3.11 -m project_brain.validate_11e_a_runway_preflight      # 25/25
py -3.11 -m project_brain.validate_11e_b_runway_api_hardening  # 24/24
py -3.11 -m project_brain.validate_11e_c_runway_browser_hardening  # 18/18
py -3.11 -m project_brain.validate_11e_d_runway_artifacts      # 20/20
py -3.11 -m project_brain.validate_11e_e_runtime_cancel_wiring  # 26/26
py -3.11 -m project_brain.validate_11e_f_runway_failover_advisory  # 26/26
py -3.11 -m project_brain.validate_11e_matrix                 # 38/38 PASS
py -3.11 -m project_brain.validate_10k_matrix                  # 89/89
```

### Regressions preserved

- **11A** capability registry, **11B** cost catalog, **11C** failover policy, **11D** provider selection
- **10J** artifact validation, **10K** operations control

All validation uses **mocks/fakes only** — no Runway API calls, no browser automation in test paths.

---

## Known Limitations

1. **Image-to-video (I2V)** — declared in 11A registry; blocked at Runway runtime (`CAPABILITY_RUNTIME_UNSUPPORTED`). Not implemented.
2. **Active API provider** — `runway` API entry remains disabled in registry; browser is default.
3. **Failover advisory** — metadata only; operator must manually choose alternate provider/requeue.
4. **Partial artifact reuse** — marked `safe_to_reuse=false` by default across providers.
5. **Hailuo/MiniMax** — no cooperative cancel mid-generation (Runway-only cancel wiring in 11E-e).

---

## Next Recommended Phase

**Option A — Hailuo Hardening (11F-style):** Apply 11E patterns (preflight, bounded waits, artifacts, cancel, advisory) to Hailuo browser/API paths.

**Option B — Image-to-Video Planning:** Design-only slice for Runway/Hailuo I2V with explicit capability gates and preflight rules before any runtime implementation.

---

## Quick Reference

| Concern | Module |
|---------|--------|
| Config | `content_brain/execution/runway_config.py` |
| Preflight | `content_brain/execution/runway_preflight.py` |
| API provider | `providers/runway_video_provider.py` |
| Browser orchestrator | `orchestrators/runway_browser_orchestrator.py` |
| Artifacts | `providers/runway_artifact_utils.py` |
| Cancel wiring | `content_brain/execution/provider_cancel_wiring.py` |
| Failover advisory | `content_brain/execution/runway_failover_advisory.py` |
| Final matrix | `project_brain/validate_11e_matrix.py` |
