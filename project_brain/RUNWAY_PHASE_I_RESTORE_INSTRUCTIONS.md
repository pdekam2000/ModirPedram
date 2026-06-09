# Runway Phase I Success — Restore Instructions

Restore point: **`RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT`**

Archive: `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip`

Use these steps to return the project to the verified working Runway Phase I FULL_AUTO 3-clip continuity state.

---

## 1. Stop running services

Stop any active ModirAgentOS processes:

1. **Backend API** — terminate the terminal running `python -m ui.api.main` (Ctrl+C or close the terminal).
2. **Frontend dev server** — if running `npm run dev` under `ui/web`, stop it.
3. **Browser automation** — close any Runway mapper / live smoke Chrome sessions launched by the project.

Wait until ports are free (default API is typically on the configured host/port in your environment).

---

## 2. Optional safety copy of current tree

Before overwriting, copy your current project folder elsewhere if you have uncommitted work you might need later.

---

## 3. Extract the backup ZIP

1. Locate:
   `C:\Users\kaman\Desktop\ModirAgentOS\storage\backups\RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip`
2. Extract **contents to the project root**, merging/overwriting files:
   `C:\Users\kaman\Desktop\ModirAgentOS`

   On Windows PowerShell (adjust paths if restoring to a different directory):

   ```powershell
   Expand-Archive -Path "C:\Users\kaman\Desktop\ModirAgentOS\storage\backups\RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip" -DestinationPath "C:\Users\kaman\Desktop\ModirAgentOS" -Force
   ```

   If `Expand-Archive` fails on very large archives, use 7-Zip or Windows Explorer “Extract All”.

3. Confirm key files exist after extract:
   - `project_brain/PHASE_IA_FIRST_SUCCESSFUL_3CLIP_RUN_REPORT.md`
   - `project_brain/runway_phase_i_3clip_last_report.json`
   - `content_brain/execution/runway_ui_navigator.py`

---

## 4. Reinstall dependencies (if needed)

From project root:

```powershell
cd C:\Users\kaman\Desktop\ModirAgentOS

# Python (use your project venv if you keep one outside the repo)
python -m pip install -r requirements.txt

# Frontend
cd ui\web
npm install
cd ..\..
```

Skip steps you know are already satisfied on the machine.

---

## 5. Restore environment secrets

The backup does **not** include `.env` or credential files.

1. Restore your `.env` (API keys, OpenAI, Runway session, etc.) from your secure store.
2. Confirm browser profile paths in config still match your machine if you use persistent Chrome profiles.

---

## 6. Restart the API

From project root:

```powershell
cd C:\Users\kaman\Desktop\ModirAgentOS
python -m ui.api.main
```

Leave this running. Restart after any later code change.

---

## 7. Restart the frontend (if used)

Development UI:

```powershell
cd C:\Users\kaman\Desktop\ModirAgentOS\ui\web
npm run dev
```

Or serve the prebuilt `ui/web/dist` if that is how you normally run the studio.

---

## 8. Run validation commands

From project root, run these validators (all should PASS on a clean restore):

```powershell
cd C:\Users\kaman\Desktop\ModirAgentOS

python project_brain/validate_phase_i_strict_completion_card_scoping.py
python project_brain/validate_phase_i_last_frame_use_frame.py
python project_brain/validate_phase_i_use_frame_handoff_verification.py
python project_brain/validate_phase_i_full_auto_mode.py
python project_brain/validate_phase_i_false_fail_while_generating.py
python project_brain/validate_runway_live_smoke_test.py
```

Optional broader checks:

```powershell
python project_brain/validate_phase_i_artifact_tracking_and_cdp_download.py
python project_brain/validate_runway_phase_i_3clip_live_continuity.py
```

---

## 9. One safe smoke test (optional but recommended)

After validators pass:

1. Open the Runway Live Smoke / Phase I panel in the UI.
2. Use **FULL_AUTO** mode with **3 clips**.
3. Hand off from Content Brain test studio or use prompts from:
   `project_brain/content_brain_test_results/latest.runway_prompts.txt`
4. Supervise the first restore verification run; confirm:
   - Clip cards scoped correctly (clip 1 / 2 / 3)
   - Use Frame @ ~9.2s between clips
   - UI shows `running` during generation (not premature FAIL)
   - Final report `ok: true`, `final_status: completed`

Reference successful baseline: `project_brain/PHASE_IA_FIRST_SUCCESSFUL_3CLIP_RUN_REPORT.md`

---

## 10. Git checkpoint (optional)

If you created the optional tag during backup:

```powershell
git checkout main
git tag -l runway-phase-i-success
```

Use the tag or this ZIP as the canonical restore point—not uncommitted experiments after the backup.

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| ZIP missing after restore | Re-copy from `storage/backups/` before extract; folder is excluded from its own archive |
| Missing `.mp4` downloads | Expected; re-run live smoke or restore clips from separate media backup |
| Import errors | Recreate `.venv` and `pip install -r requirements.txt` |
| UI stale FAIL while running | Confirm `ui/api/runway_live_smoke_service.py` and approval panel match restored version |
| Use Frame click fails | Confirm `runway_ui_map.json` and navigator files match restored versions |

---

## Support documents

- Manifest: `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_manifest.md`
- Backup report: `project_brain/RUNWAY_PHASE_I_SUCCESS_BACKUP_REPORT.md`
- Success run write-up: `project_brain/PHASE_IA_FIRST_SUCCESSFUL_3CLIP_RUN_REPORT.md`
