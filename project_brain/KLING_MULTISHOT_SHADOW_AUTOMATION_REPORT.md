# Kling Multishot Shadow Automation Report

**Phase:** KLING-MULTISHOT-SHADOW-AUTOMATION  
**Strategy:** 2-shot continuity (12s action + 3s bridge = 15s clip)  
**Mode:** Shadow / dry-run only — no Generate click, no credits spent  
**Date:** 2026-06-16

---

## Summary

Shadow automation for Kling Multishot is implemented using the canonical 2-shot continuity architecture from `project_brain/KLING_STORY_ARCHITECTURE_DESIGN.md` and the relabeled UI map at `project_brain/runway_ui_mapping/runway_ui_map.json`.

Static validation passes all 10 checks. Map-only dry-run passes. Live CDP connected to Runway but stopped safely at step 01 when the mapped `provider_kling_3_pro` React ID was not visible (expected stale-ID behavior; no UI actions beyond tab detection).

---

## Files Created

| File | Purpose |
|------|---------|
| `tools/kling_multishot_shadow_runner.py` | CDP shadow runner — configures 2-shot Multishot UI, stops before Generate |
| `content_brain/execution/kling_multishot_config.py` | 2-shot continuity constants, required/optional labels, blocklist |
| `content_brain/execution/kling_multishot_map_loader.py` | Kling-specific map loader with approval gate + selector validation |
| `project_brain/validate_kling_multishot_shadow_runner.py` | 10-test validation suite |
| `project_brain/KLING_MULTISHOT_SHADOW_AUTOMATION_REPORT.md` | This report |

## Files Modified

| File | Change |
|------|--------|
| `tools/kling_multishot_shadow_runner.py` | Fixed first-frame upload (single click + file chooser fallback) |

No changes to `runway_ui_map.json` in this phase (relabel P0 already applied).

---

## Labels Used (Required)

| Label | Role |
|-------|------|
| `provider_kling_3_pro` | Select Kling 3.0 Pro provider |
| `multishot_tab` | Switch to Multishot mode |
| `audio_toggle_on` | Confirm audio enabled |
| `first_frame_upload` | Optional first-frame image upload |
| `shot_1_prompt` | Main story action prompt (12s) |
| `shot_2_prompt` | Transition bridge prompt (3s) |
| `shot_1_duration_menu` | Open Shot 1 duration menu |
| `shot_1_duration_12s` | Set Shot 1 to 12s |
| `shot_2_duration_menu` | Open Shot 2 duration menu |
| `shot_2_duration_3s` | Confirm Shot 2 at 3s |
| `generate_button` | Verified visible + approval-gated; **not clicked** |

## Labels Not Required (Optional / Future)

`add_shot_button`, `shot_3_prompt`, `shot_4_prompt`, `shot_5_prompt` — present in map but excluded from required resolution; runner never uses Add Shot in default flow.

---

## Duration Strategy

| Setting | Value |
|---------|-------|
| Strategy | `two_shot_continuity` |
| Clip total | 15 seconds |
| Shot 1 | 12s — main story action |
| Shot 2 | 3s — transition bridge / next-scene setup |
| Add Shot | **Not used** |
| 5-shot mode | **Not used** |

---

## Safety Confirmations

| Check | Result |
|-------|--------|
| `dry_run=True` only (raises if false) | Enforced |
| `generate_button` in `safety.requires_approval` | Yes |
| Generate clicked | **No** (`generate_clicked: false`) |
| Credits spent | **No** (`credits_spent: false`) |
| Add Shot used | **No** (`add_shot_used: false`) |
| Missing required selector | Stops with error (map precheck) |
| Duration unverified | Stops before Generate (live path) |
| Approval gate missing | Stops with error |

---

## Dry-Run Results

### Static validation

```text
python project_brain/validate_kling_multishot_shadow_runner.py
→ All 10 checks passed
```

Tests covered:

1. UI map loads  
2. Required 2-shot labels exist  
3. Optional 5-shot labels not required  
4. Generate label requires approval  
5. Runner has dry-run guard  
6. Runner never clicks Generate in dry-run (mock CDP)  
7. 2-shot continuity config used  
8. Shot 1 = 12s  
9. Shot 2 = 3s  
10. Relabel validation still passes (17/17 from P0 summary)

### Map-only dry-run

```text
python tools/kling_multishot_shadow_runner.py --map-only \
  --shot-1-prompt "..." --shot-2-prompt "..."
→ ok: true, generate_clicked: false, credits_spent: false
```

### Live CDP attempt

```text
python tools/kling_multishot_shadow_runner.py \
  --shot-1-prompt "..." --shot-2-prompt "..."
→ CDP connected (127.0.0.1:9222), Runway tab found
→ Failed at provider_kling_3_pro visibility (stale React aria ID)
→ generate_clicked: false, credits_spent: false (safe stop)
```

**Note:** Live UI automation requires a fresh mapper scan when React IDs rotate. Map structure and safety gates are validated; runtime selector refresh is a follow-up for the live phase.

---

## Runner Flow (Shadow)

1. Validate UI map + approval gate  
2. Connect Chrome CDP  
3. Select `provider_kling_3_pro`  
4. Select `multishot_tab`  
5. Confirm `audio_toggle_on`  
6. Upload first frame (if path provided)  
7. Set Shot 1 duration → 12s  
8. Confirm Shot 2 duration → 3s  
9. Fill `shot_1_prompt`, `shot_2_prompt`  
10. Verify `generate_button` exists and is approval-gated  
11. **Stop** — Generate not clicked  

---

## Next Phase

**PHASE KLING-MULTISHOT-LIVE-APPROVAL-GATED** (after approval):

- Refresh stale React IDs via mapper scan if needed  
- Complete live CDP shadow through step 10 on current Runway UI  
- Wire explicit human approval gate before any Generate click  
- Still no auto-Generate without approval  

---

## References

- `project_brain/KLING_STORY_ARCHITECTURE_DESIGN.md`  
- `project_brain/runway_ui_mapping/runway_ui_map.json`  
- `project_brain/KLING_MULTISHOT_RELABEL_REPORT.md`  
- `tools/kling_multishot_shadow_runner.py`  
