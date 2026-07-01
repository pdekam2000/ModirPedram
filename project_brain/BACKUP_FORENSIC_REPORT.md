# Backup Forensic Report

Generated: 2026-06-13T09:39:08.652648+00:00
Scanner: `backup_forensic_scan_v2`
Scope: `C:\Users\kaman\Desktop\ModirAgentOS\storage\backups`

## Executive summary

- **Total backup folder size:** 319.23 GB (342,767,304,937 bytes)
- **Total backup files:** 18
- **Primary cause of 319 GB footprint:** uncontrolled full-project ZIP `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_171831.zip` at 310.36 GB
- **Intended controlled restore point:** `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip` at 8.87 GB
- **Estimated reclaimable after review:** 310.36 GB

### Key finding on 310 GB file

The 310 GB file **starts with a valid ZIP local header (`PK\x03\x04`)** but has **no valid end-of-central-directory record**. It is an **aborted / incomplete ZIP write** from the first restore-point attempt, not a restorable archive. Standard unzip tools will report it as corrupt.

**Disk layout:** only the first ~4.4 GB is sequential ZIP structure (3,731 local headers). The remaining **~306 GB is an orphan trailing write blob** with no ZIP framing — raw bytes appended after the last local header (`weights.bin` with `comp_size=0xFFFFFFFF`). That blob is high-entropy, unindexed data and cannot be extracted without the missing central directory.

**Timeline note:** file modified until `2026-06-09T17:16:01Z`, ~92 minutes after the controlled restore point (`173154.zip`) finished at `15:44:25Z` — suggesting the first backup writer kept appending data in the background.

## Why the 310 GB backup exists

The file `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_171831.zip` is **310.36 GB** on disk with **3,731** parseable local headers.
Structured ZIP portion: **4.36 GB** | Trailing orphan blob: **306.00 GB**.
Uncompressed payload in structured portion: **4.56 GB** (compressed on-disk in structured portion: **4.36 GB**).

### Root cause

This matches the **first failed Runway Phase I restore-point attempt** documented in `project_brain/RUNWAY_PHASE_I_SUCCESS_BACKUP_REPORT.md`: an initial backup ran **without the controlled exclusion list** and ballooned by including large project trees that the final backup deliberately excludes. The report notes a partial archive was intended to be deleted; this 310 GB file is the surviving aborted artifact — mostly an unindexed trailing write, not a restorable archive.

The backup script `tools/create_runway_phase_i_restore_point.py` is designed to exclude:

- `storage/backups/` (avoid nested backups)
- `*.mp4`, `*.webm`, `*.mov`, `*.mkv`, `*.zip`
- `.git`, `venv`, `node_modules`, `chrome_mapper_profile`, caches

The 310 GB archive **violates those intentions** and contains large trees the controlled backup omits.

### Contents detected inside the 310 GB ZIP

- **incomplete_or_aborted_zip_missing_eocd**
- **assets/videos**
- **nested_backups**

#### Top-level folders inside ZIP (by uncompressed bytes)

| Folder | Files | Uncompressed size |
|--------|------:|------------------:|
| `backup_temp` | 3,681 | 4.51 GB |
| `backups` | 1 | 38.46 MB |
| `assets` | 1 | 3.46 MB |
| `project_tree.txt` | 1 | 1.64 MB |
| `agents` | 15 | 95.56 KB |
| `test_full_ai_video_pipeline.py` | 1 | 18.20 KB |
| `automation` | 2 | 12.23 KB |
| `main.py` | 1 | 5.10 KB |
| `full_selfcare_factory.py` | 1 | 4.98 KB |
| `rebuild_existing_project.py` | 1 | 4.47 KB |
| `postprocess_existing_video.py` | 1 | 1.49 KB |
| `test_clip_audio_sync.py` | 1 | 1.41 KB |
| `test_full_hailuo_pipeline.py` | 1 | 1.29 KB |
| `requirements.txt` | 1 | 1.20 KB |
| `test_timeline_voice.py` | 1 | 1.18 KB |
| `test_continuity_hailuo_pipeline.py` | 1 | 1.12 KB |
| `test_episode_preview.py` | 1 | 1.09 KB |
| `test_ffmpeg_stitch.py` | 1 | 1.07 KB |
| `test_continuity_engine.py` | 1 | 969.00 B |
| `test_runway_orchestrator_direct.py` | 1 | 846.00 B |
| `.gitignore` | 1 | 824.00 B |
| `test_content_series_planner.py` | 1 | 774.00 B |
| `test_final_cinematic_assembly.py` | 1 | 771.00 B |
| `test_multi_clip.py` | 1 | 765.00 B |
| `test_selfcare_content_engine.py` | 1 | 746.00 B |

#### Largest individual entries

- `backup_temp/storage/real_chrome_profile/OptGuideOnDeviceModel/2025.8.8.1141/weights.bin` — 4.00 GB
- `backup_temp/storage/real_chrome_profile/OptGuideOnDeviceClassifierModel/2026.2.12.1554/weights.bin` — 120.19 MB
- `backups/ModirAgentOS_BACKUP_20260519_215615.zip` — 38.46 MB
- `backup_temp/storage/real_chrome_profile/component_crx_cache/22fb5e3e997b6c5e2194c69fe572415a2333a34bf23165ca71336b2fdc4dbb34` — 21.97 MB
- `backup_temp/storage/real_chrome_profile/Default/Cache/Cache_Data/data_3` — 12.01 MB
- `backup_temp/storage/real_chrome_profile/Default/Cache/Cache_Data/data_2` — 11.01 MB
- `backup_temp/storage/real_chrome_profile/GrShaderCache/data_3` — 8.01 MB
- `backup_temp/storage/real_chrome_profile/component_crx_cache/3c490cd0abb97f15040e4aaa68dc4f1eae73b73591c29ae082ea6c5b364abe94` — 7.43 MB
- `backup_temp/storage/real_chrome_profile/OnDeviceHeadSuggestModel/20251024.824731831.14/cr_de_500000_index.bin` — 7.43 MB
- `backup_temp/storage/real_chrome_profile/Default/Cache/Cache_Data/f_0000f7` — 7.22 MB
- `backup_temp/storage/real_chrome_profile/de-DE-3-0.bdic` — 6.50 MB
- `backup_temp/storage/real_chrome_profile/Default/Cache/Cache_Data/f_000001` — 6.50 MB
- `backup_temp/storage/real_chrome_profile/Default/Cache/Cache_Data/f_000192` — 6.00 MB
- `backup_temp/storage/browser_session/Default/Cache/Cache_Data/data_3` — 4.01 MB
- `backup_temp/storage/browser_session/GrShaderCache/data_3` — 4.01 MB

- Nested ZIP files inside archive: **1** (38.46 MB uncompressed)
- Video files inside archive: **0** (0.00 B uncompressed)
- **outputs/runs:** not in top-level structured headers; may exist inside trailing blob (unverified)
- **downloads/runway:** not detected in structured portion
- **nested backups:** 1 nested `.zip` inside structured portion (`backups/ModirAgentOS_BACKUP_20260519_215615.zip`, 38.46 MB)

## Controlled 8.87 GB restore point

`storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip` contains **18,165** files, **10.96 GB** uncompressed.

Detected content flags:

- outputs/runs
- downloads/runway
- assets/videos
- storage/backups
- project_brain

Top-level folders:

- `storage` — 5.12 GB (10,528 files)
- `backup_temp` — 4.63 GB (3,820 files)
- `project_brain` — 1.19 GB (3,181 files)
- `outputs` — 10.20 MB (188 files)
- `assets` — 3.46 MB (1 files)
- `content_brain` — 2.98 MB (167 files)
- `project_tree.txt` — 1.64 MB (1 files)
- `ui` — 1.01 MB (114 files)
- `downloads` — 480.88 KB (1 files)
- `providers` — 139.55 KB (21 files)
- `core` — 124.33 KB (26 files)
- `tools` — 114.79 KB (2 files)
- `agents` — 95.56 KB (15 files)
- `execution` — 92.03 KB (22 files)
- `engines` — 87.60 KB (26 files)

## Top 50 largest backup files

| Rank | File | Size | Created (UTC) | Modified (UTC) | SHA256 |
|-----:|------|-----:|---------------|----------------|--------|
| 1 | `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_171831.zip` | 310.36 GB | 2026-06-09T15:18:31.414414+00:00 | 2026-06-09T17:16:01.880255+00:00 | `partial:700bda7f…` |
| 2 | `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip` | 8.87 GB | 2026-06-09T15:31:54.790090+00:00 | 2026-06-09T15:44:25.062926+00:00 | `partial:11999a85…` |
| 3 | `storage/backups/pipelines.full_video_pipeline.bak` | 18.25 KB | 2026-05-26T20:30:30.981482+00:00 | 2026-05-20T17:03:58.195803+00:00 | `5d0cd191b61290d8…` |
| 4 | `storage/backups/providers__runway_video_provider.py.20260526_173217.bak` | 5.71 KB | 2026-05-26T15:32:17.395216+00:00 | 2026-05-26T15:17:28.369365+00:00 | `6197b1e23a901294…` |
| 5 | `storage/backups/providers__runway_video_provider.py.20260526_171728.bak` | 5.64 KB | 2026-05-26T15:17:28.368364+00:00 | 2026-05-21T17:03:26.397636+00:00 | `a6c888a5a9b24426…` |
| 6 | `storage/backups/main.py.20260515_221126.bak` | 2.23 KB | 2026-05-15T20:11:26.481168+00:00 | 2026-05-15T20:02:57.180365+00:00 | `4e41436d716c39ec…` |
| 7 | `storage/backups/upgrades/example_upgrade_20260609_183541.manifest.json` | 1.46 KB | 2026-06-09T16:35:41.354315+00:00 | 2026-06-09T16:35:41.368319+00:00 | `eb5025c68bf23db5…` |
| 8 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_220717.bak` | 235.00 B | 2026-05-27T20:07:17.736910+00:00 | 2026-05-27T19:58:14.231871+00:00 | `ec7d242bfe8d41d2…` |
| 9 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_213712.bak` | 132.00 B | 2026-05-27T19:37:12.348208+00:00 | 2026-05-27T19:03:16.389751+00:00 | `a1c22c1d16ec604a…` |
| 10 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_210316.bak` | 127.00 B | 2026-05-27T19:03:16.388750+00:00 | 2026-05-27T18:59:09.325243+00:00 | `f4f739c4ca0d21f8…` |
| 11 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_204657.bak` | 126.00 B | 2026-05-27T18:46:57.716914+00:00 | 2026-05-27T15:19:16.900538+00:00 | `0d565be4610fcb8c…` |
| 12 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_205116.bak` | 125.00 B | 2026-05-27T18:51:16.965632+00:00 | 2026-05-27T18:46:57.717908+00:00 | `f48efe6b59f75c25…` |
| 13 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_205909.bak` | 125.00 B | 2026-05-27T18:59:09.324244+00:00 | 2026-05-27T18:51:16.966623+00:00 | `fb980f062ca28d88…` |
| 14 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_214742.bak` | 118.00 B | 2026-05-27T19:47:42.348264+00:00 | 2026-05-27T19:37:12.349207+00:00 | `6a9f0e2447d69a30…` |
| 15 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_215814.bak` | 116.00 B | 2026-05-27T19:58:14.230880+00:00 | 2026-05-27T19:47:42.349277+00:00 | `ef2c8d4504d1d408…` |
| 16 | `storage/backups/execution__apply_replace_patch_test_target.py.20260527_171916.bak` | 107.00 B | 2026-05-27T15:19:16.899540+00:00 | 2026-05-27T15:19:16.895035+00:00 | `8f4c002a16e7ff36…` |
| 17 | `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173137.zip` | 22.00 B | 2026-06-09T15:31:37.011981+00:00 | 2026-06-09T15:31:37.012981+00:00 | `8739c76e681f9009…` |
| 18 | `storage/backups/upgrades/example_upgrade_20260609_183541.zip` | 22.00 B | 2026-06-09T16:35:41.353315+00:00 | 2026-06-09T16:35:41.367318+00:00 | `8739c76e681f9009…` |

## Top 20 largest backup folders

| Rank | Folder | Size | Files | Last modified (UTC) |
|-----:|--------|-----:|------:|---------------------|
| 1 | `storage/backups` | 319.23 GB | 18 | 2026-06-09T17:16:01.880255+00:00 |
| 2 | `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_171831.zip` | 310.36 GB | 1 | 2026-06-09T17:16:01.880255+00:00 |
| 3 | `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip` | 8.87 GB | 1 | 2026-06-09T15:44:25.062926+00:00 |
| 4 | `storage/backups/pipelines.full_video_pipeline.bak` | 18.25 KB | 1 | 2026-05-20T17:03:58.195803+00:00 |
| 5 | `storage/backups/providers__runway_video_provider.py.20260526_173217.bak` | 5.71 KB | 1 | 2026-05-26T15:17:28.369365+00:00 |
| 6 | `storage/backups/providers__runway_video_provider.py.20260526_171728.bak` | 5.64 KB | 1 | 2026-05-21T17:03:26.397636+00:00 |
| 7 | `storage/backups/main.py.20260515_221126.bak` | 2.23 KB | 1 | 2026-05-15T20:02:57.180365+00:00 |
| 8 | `storage/backups/upgrades` | 1.48 KB | 2 | 2026-06-09T16:35:41.368319+00:00 |
| 9 | `storage/backups/upgrades/example_upgrade_20260609_183541.manifest.json` | 1.46 KB | 1 | 2026-06-09T16:35:41.368319+00:00 |
| 10 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_220717.bak` | 235.00 B | 1 | 2026-05-27T19:58:14.231871+00:00 |
| 11 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_213712.bak` | 132.00 B | 1 | 2026-05-27T19:03:16.389751+00:00 |
| 12 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_210316.bak` | 127.00 B | 1 | 2026-05-27T18:59:09.325243+00:00 |
| 13 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_204657.bak` | 126.00 B | 1 | 2026-05-27T15:19:16.900538+00:00 |
| 14 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_205116.bak` | 125.00 B | 1 | 2026-05-27T18:46:57.717908+00:00 |
| 15 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_205909.bak` | 125.00 B | 1 | 2026-05-27T18:51:16.966623+00:00 |
| 16 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_214742.bak` | 118.00 B | 1 | 2026-05-27T19:37:12.349207+00:00 |
| 17 | `storage/backups/__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_215814.bak` | 116.00 B | 1 | 2026-05-27T19:47:42.349277+00:00 |
| 18 | `storage/backups/execution__apply_replace_patch_test_target.py.20260527_171916.bak` | 107.00 B | 1 | 2026-05-27T15:19:16.895035+00:00 |
| 19 | `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173137.zip` | 22.00 B | 1 | 2026-06-09T15:31:37.012981+00:00 |
| 20 | `storage/backups/upgrades/example_upgrade_20260609_183541.zip` | 22.00 B | 1 | 2026-06-09T16:35:41.367318+00:00 |

## Size threshold counts

- **>5GB:** 2 file(s), combined 319.23 GB
  - `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_171831.zip` — 310.36 GB (created 2026-06-09T15:18:31.414414+00:00, modified 2026-06-09T17:16:01.880255+00:00)
  - `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip` — 8.87 GB (created 2026-06-09T15:31:54.790090+00:00, modified 2026-06-09T15:44:25.062926+00:00)
- **>10GB:** 1 file(s), combined 310.36 GB
  - `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_171831.zip` — 310.36 GB (created 2026-06-09T15:18:31.414414+00:00, modified 2026-06-09T17:16:01.880255+00:00)
- **>50GB:** 1 file(s), combined 310.36 GB
  - `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_171831.zip` — 310.36 GB (created 2026-06-09T15:18:31.414414+00:00, modified 2026-06-09T17:16:01.880255+00:00)

## Backup chains

### `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT`
- Pattern: `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_YYYYMMDD_HHMMSS.zip`
- Chain type: **full_backup_chain** | incremental: **False**

| Member | Size | Modified | Classification |
|--------|-----:|----------|----------------|
| `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_171831.zip` | 310.36 GB | 2026-06-09T17:16:01.880255+00:00 | duplicate_full_backup_uncontrolled |
| `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173137.zip` | 22.00 B | 2026-06-09T15:31:37.012981+00:00 | corrupt_or_empty_stub |
| `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip` | 8.87 GB | 2026-06-09T15:44:25.062926+00:00 | full_backup_controlled |

### `providers__runway_video_provider.py`
- Pattern: `providers__runway_video_provider.py*.bak`
- Chain type: **incremental_file_backup** | incremental: **True**

| Member | Size | Modified | Classification |
|--------|-----:|----------|----------------|
| `providers__runway_video_provider.py.20260526_171728.bak` | 5.64 KB | 2026-05-21T17:03:26.397636+00:00 | incremental_backup |
| `providers__runway_video_provider.py.20260526_173217.bak` | 5.71 KB | 2026-05-26T15:17:28.369365+00:00 | incremental_backup |

### `__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py`
- Pattern: `__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py*.bak`
- Chain type: **incremental_file_backup** | incremental: **True**

| Member | Size | Modified | Classification |
|--------|-----:|----------|----------------|
| `__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_204657.bak` | 126.00 B | 2026-05-27T15:19:16.900538+00:00 | incremental_backup |
| `__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_205116.bak` | 125.00 B | 2026-05-27T18:46:57.717908+00:00 | incremental_backup |
| `__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_205909.bak` | 125.00 B | 2026-05-27T18:51:16.966623+00:00 | incremental_backup |
| `__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_210316.bak` | 127.00 B | 2026-05-27T18:59:09.325243+00:00 | incremental_backup |
| `__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_213712.bak` | 132.00 B | 2026-05-27T19:03:16.389751+00:00 | incremental_backup |
| `__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_214742.bak` | 118.00 B | 2026-05-27T19:37:12.349207+00:00 | incremental_backup |
| `__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_215814.bak` | 116.00 B | 2026-05-27T19:47:42.349277+00:00 | incremental_backup |
| `__Users__kaman__Desktop__ModirAgentOS__execution__apply_replace_patch_test_target.py.20260527_220717.bak` | 235.00 B | 2026-05-27T19:58:14.231871+00:00 | incremental_backup |


## Identical backups (SHA256)

- `8739c76e681f900923b900c9df0ef75cf421d39cabb54650c4b9ad19b6a76d85` → `storage/backups/RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173137.zip`, `storage/backups/upgrades/example_upgrade_20260609_183541.zip`

## Reclaim estimate

**310.36 GB**

- Remove superseded restore point `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_171831.zip` (310.36 GB) after confirming `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip` restores correctly.
- Remove superseded restore point `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173137.zip` (22.00 B) after confirming `RUNWAY_PHASE_I_SUCCESS_RESTORE_POINT_20260609_173154.zip` restores correctly.
- Obsolete tiny .bak patch backups (~14.76 KB).
