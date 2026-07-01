# pwmap — Runway browser automation runtime (vendored)

This folder is the **canonical pwmap source inside ModirAgentOS**. It contains the repaired feed-scoped download selection runtime used by Product Studio (`content_brain/execution/pwmap_runway_agent_adapter.py`).

## Layout

| Path | Purpose |
|------|---------|
| `runway_agent.py` | Main Runway/Kling multi-clip browser agent |
| `download_selection.py` | Output snapshots, stale-source rejection, duplicate MP4 guard |
| `pwmap.py` | Legacy pwmap mapper utilities |
| `agent_inbox/*.example.json` | Example job payloads (copy to `job.json` for live runs) |
| `requirements.txt` | Python deps (`playwright`, etc.) |

## Runtime resolution

ModirAgentOS picks the pwmap root in this order:

1. **`MODIR_PWMAP_ROOT`** environment variable (explicit override)
2. **`C:\Users\kaman\Desktop\pwmap`** if present (typical local production install with browser profile + downloads)
3. **`external/pwmap`** in this repo (default for clean checkouts and tooling)

To force the vendored copy on a machine that also has Desktop pwmap:

```powershell
$env:MODIR_PWMAP_ROOT = "C:\Users\kaman\Desktop\ModirAgentOS\external\pwmap"
```

## Local-only paths (never commit)

These are gitignored under `external/pwmap/`:

- `runway_downloads/` — generated MP4 outputs
- `pwmap_profile/` — Chrome session / login profile
- `agent_inbox/job.json`, `agent_inbox/batch.json` — live job payloads

## Setup

```powershell
cd external\pwmap
pip install -r requirements.txt
playwright install chrome
python runway_agent.py --open-browser
```

Log in to Runway once; session is stored in `pwmap_profile/` (local only).

## Download selection repair

Clip 2+ downloads use feed-scoped video URLs and pre/post output snapshots. See `project_brain/PWMAP_DOWNLOAD_SELECTION_REPAIR_REPORT.md` in the main repo.
