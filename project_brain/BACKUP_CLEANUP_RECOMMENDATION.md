# Backup Cleanup Recommendation

Generated: 2026-06-13T09:39:08.653476+00:00

> **DO NOT DELETE. DO NOT MOVE.** Advisory report only.

## Recommended keep set

- **Keep:** `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip`
- **Keep:** `project_brain/RUNWAY_PHASE_I_RESTORE_INSTRUCTIONS.md` and git tag `runway-phase-i-success`
- **Keep:** small `.bak` files only if you still need patch rollback history

## Safe reclaim candidates (after human confirmation)

Estimated reclaimable: **310.36 GB**

1. **`RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_171831.zip` (310.36 GB)** — LIKELY SAFE TO ARCHIVE OFFSITE OR DELETE
   - Uncontrolled duplicate of project state
   - Superseded by controlled 8.87 GB restore point
   - Contains large excluded trees (.git, chrome profiles, nested zips, media)

2. **`RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173137.zip` (22 bytes)** — SAFE TO DELETE
   - Empty/corrupt stub from interrupted backup attempt

3. **Tiny `.bak` patch backups (<10 KB)** — LIKELY SAFE
   - Old single-file patch backups from May–June 2025

## DO NOT DELETE without explicit approval

- `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip` (8.87 GB) — canonical restore point
- Any backup you have not test-restored in a sandbox folder

## Why 310 GB happened (short version)

An uncontrolled full-project ZIP was started before exclusion rules were applied. Only **~4.4 GB** of the file is parseable ZIP structure (mostly `backup_temp/` Chrome profile caches and one nested 38 MB backup). **~306 GB** is an orphan trailing write blob with no ZIP headers — likely continued raw dumping from the aborted backup process (possibly `.git`, media, or self-including the in-progress archive). The controlled **8.87 GB** restore point (`173154.zip`) supersedes it and uses `tools/create_runway_phase_i_restore_point.py` exclusions.

## Suggested next phase (manual)

1. Verify restore from `...173154.zip` in a scratch directory
2. Copy the 310 GB ZIP to external cold storage **or** delete after checksum note recorded
3. Re-run `python project_brain/backup_forensic_scan.py` to confirm new total

## 310 GB ZIP composition snapshot

- Structured ZIP portion: 4.36 GB
- Trailing orphan blob: 306.00 GB

Top-level folders in structured portion:
- `backup_temp`: 4.51 GB
- `backups`: 38.46 MB
- `assets`: 3.46 MB
- `project_tree.txt`: 1.64 MB
- `agents`: 95.56 KB
- `test_full_ai_video_pipeline.py`: 18.20 KB
- `automation`: 12.23 KB
- `main.py`: 5.10 KB
- `full_selfcare_factory.py`: 4.98 KB
- `rebuild_existing_project.py`: 4.47 KB
