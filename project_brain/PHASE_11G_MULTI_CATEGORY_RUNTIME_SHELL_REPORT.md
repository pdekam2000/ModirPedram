# Phase 11G — Multi-Category Runtime Shell Report

Generated: 2026-05-28

## Summary

Phase 11G adds a **multi-category runtime shell** to Content Brain Provider Runtime. Five media categories are defined with normalized per-category slots. **Only video dispatch/execution remains active** — voice, music, subtitles, and assembly are read-only `planned` placeholders with documented future routing hooks.

**Validation:** `python -m project_brain.validate_11g_multi_category_runtime_shell` → **20/20 PASS**  
**UI build:** `npm run build` (Execution Center) → **PASS**

---

## Files Analyzed

| File | Role |
|------|------|
| `content_brain/execution/provider_runtime_engine.py` | Video dispatch lifecycle; category_runtime writer |
| `content_brain/execution/provider_categories.py` | Category constants (10I) |
| `content_brain/execution/session_store.py` | Session persistence |
| `content_brain/providers/provider_capability_registry.py` | Capability registry (11A) |
| `content_brain/providers/provider_selection_engine.py` | Provider selection (11D) |
| `ui/api/services/runtime_service.py` | Runtime status API |
| `ui/api/services/panel_extractor.py` | Provider runtime panel DTO |
| `ui/api/schemas/runtime.py` | Status response schema |
| `ui/web/src/components/RuntimeObservability.tsx` | Execution Center runtime UI |
| `storage/content_brain/execution/sessions/*.json` | Legacy session shapes |

---

## Files Changed

| File | Change |
|------|--------|
| `content_brain/execution/category_runtime_compat.py` | **NEW** — shell schema, safe reads, future router hooks |
| `content_brain/execution/provider_categories.py` | Extended categories: `subtitles`, `assembly`; delegates defaults to compat |
| `content_brain/execution/provider_runtime_engine.py` | Calls `ensure_multi_category_shell()` on dispatch; policy snapshot 11G fields |
| `ui/api/services/runtime_service.py` | Adds `category_runtime_slots` to status response |
| `ui/api/services/panel_extractor.py` | Adds `category_runtime_slots` to provider runtime panel |
| `ui/api/schemas/runtime.py` | `CategoryRuntimeSlotStatus` + response field |
| `ui/web/src/utils/categoryRuntimeShell.ts` | **NEW** — client-side slot resolution |
| `ui/web/src/components/CategoryRuntimeSlotsPanel.tsx` | **NEW** — read-only category grid |
| `ui/web/src/components/RuntimeObservability.tsx` | Renders category shell panel |
| `ui/web/src/api/client.ts` | TypeScript types for category slots |
| `ui/web/src/App.css` | Category shell styles |
| `project_brain/validate_11g_multi_category_runtime_shell.py` | **NEW** — 20-test validator |
| `project_brain/PHASE_11G_MULTI_CATEGORY_RUNTIME_SHELL_REPORT.md` | This report |

**Not changed:** Runway/Hailuo providers, browser automation, legacy `full_video_pipeline.py`, `TimelineEngine`, voice/subtitle/assembly execution engines.

---

## Schema Extension

### Media categories (11G)

| Key | Short name | Default status | Default provider | Executable |
|-----|------------|----------------|------------------|------------|
| `video_generation` | video | pending | (from session) | **Yes** |
| `voice_generation` | voice | planned | elevenlabs | No |
| `music_generation` | music | planned | suno | No |
| `subtitles` | subtitles | planned | internal | No |
| `assembly` | assembly | planned | internal | No |

Legacy keys `image_generation` and `publishing` remain readable on old sessions (mapped to `skipped` when present); they are **not** included in new default shells.

### Per-category slot shape

```json
{
  "category_name": "voice",
  "status": "planned",
  "provider": "elevenlabs",
  "artifacts": [],
  "error": null,
  "started_at": null,
  "completed_at": null,
  "duration_seconds": null,
  "cost_estimate": null,
  "runtime_notes": [],
  "state": "not_started"
}
```

Status values: `planned` | `pending` | `running` | `completed` | `failed` | `skipped`

The legacy `state` field is preserved for existing video dispatch code paths (`RUNNING`, `COMPLETED`, etc.). API/UI normalization maps `state` → `status` on read.

### Execution runtime shell metadata

New block written on dispatch:

```json
"multi_category_shell": {
  "shell_version": "11g_v1",
  "media_categories": ["video_generation", "voice_generation", "music_generation", "subtitles", "assembly"],
  "future_routers": {
    "voice_generation": "content_brain.execution.voice_provider_router.VoiceProviderRouter",
    "music_generation": "content_brain.execution.music_provider_router.MusicProviderRouter",
    "subtitles": "content_brain.execution.subtitle_runtime.SubtitleRuntime",
    "assembly": "content_brain.execution.assembly_runtime.AssemblyRuntime"
  },
  "executable_categories_11g": ["video_generation"]
}
```

---

## Backward Compatibility

- **Legacy sessions** without `subtitles` / `assembly` slots normalize safely via `normalize_category_runtime()` — no crashes, defaults to `planned`.
- **Legacy `state` field** on video slots unchanged; video dispatch still writes `state`, `started_at`, `completed_at`, `artifact_count` as before.
- **Legacy `image_generation` / `publishing`** slots on old JSON still parse; excluded from new 5-category UI view.
- **`get_category_slot()`** returns defaults (`planned`, `—` provider) when fields are missing.
- **`build_category_runtime_view()`** used by API/UI — read-only normalization, no mutation of stored sessions except via new dispatches.

---

## Video Runtime Unchanged

Confirmed:

- `ProviderRuntimeEngine.validate_dispatch_eligibility()` still accepts **video only** (`CATEGORY_NOT_SUPPORTED` for other categories).
- `_execute_clips()` / `VideoProviderRouter` path untouched.
- Runway/Hailuo cancel, failover advisory, artifact validation flows unchanged.
- Only additive change in engine: `ensure_multi_category_shell()` after building `execution_runtime` on dispatch (placeholder slots + metadata).

---

## No Voice / Music / Subtitle / Assembly Execution

Confirmed:

- No imports of `NarrationEngine`, `full_video_pipeline`, `TimelineEngine`, `subtitle_engine`, or `final_assembly_engine`.
- No new provider routers implemented — only string constants in `FUTURE_CATEGORY_ROUTERS`.
- Non-video categories remain `status: planned` with zero artifacts.

---

## Execution Center UI

- **CategoryRuntimeSlotsPanel** shows all five categories as read-only cards (status, provider, artifact count).
- Data source: `GET /sessions/{id}/runtime/status` → `category_runtime_slots`, with fallback from session panel.
- No dispatch buttons or execution controls added for non-video categories.

---

## Compatibility Helpers

| Helper | Purpose |
|--------|---------|
| `default_category_slot()` | Empty slot with all required fields |
| `default_category_runtime_slots()` | All 5 category defaults |
| `normalize_category_slot()` | Safe single-slot merge |
| `normalize_category_runtime()` | Full map for session reads |
| `get_category_slot()` | Safe per-category read from session |
| `ensure_multi_category_shell()` | Merge shell into runtime on dispatch |
| `build_category_runtime_view()` | Ordered list for API/UI |

---

## Next Recommended Slice

**Phase 11H — VoiceProviderRouter + ElevenLabs hardening**

1. Implement `VoiceProviderRouter` at documented hook path.
2. Add `SessionNarrationAdapter` (Content Brain brief → narration segments; **not** Selfcare TimelineEngine).
3. Wire voice category dispatch behind 11G shell with preflight, artifact validation, failure taxonomy (mirror 11E/11F Runway/Hailuo pattern).
4. Update `executable_categories_11g` to include `voice_generation` when ready.
5. Defer subtitles/assembly modernization to Phase 11H+ / 11I.

---

## Validator

```bash
python -m project_brain.validate_11g_multi_category_runtime_shell
```

Tests cover: category definitions, slot schema, legacy normalization, shell metadata, future router hooks, non-video dispatch rejection, API/panel integration, policy snapshot.
