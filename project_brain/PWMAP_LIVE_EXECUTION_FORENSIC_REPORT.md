# PWMAP Live Execution Forensic Report

**Date:** 2026-06-23  
**Phase:** PWMAP-LIVE-EXECUTION-FORENSIC  
**Scope:** Read-only analysis — no Product Studio / planner / routing / Use Frame / browser changes.

---

## Executive Summary

The first real Product Studio multi-clip execution **failed immediately** (exit code 1) because the pwmap subprocess was launched with a **Python interpreter that does not have `playwright` installed**. This is an **environment mismatch**, not a Product Studio orchestration bug.

| Field | Value |
|-------|-------|
| **Failed run ID** | `pwmap_20260623T204859_324bf879` |
| **Also failed** | `pwmap_20260623T204719_a0256aad` (same error) |
| **Last success** | `pwmap_20260623T200804_256fb07a` (single-clip smoke, ~16 min) |
| **Root cause** | `ModuleNotFoundError: No module named 'playwright'` |
| **Failing file** | `C:\Users\kaman\Desktop\pwmap\runway_agent.py` line 28 |

---

## 1. Exact Subprocess Command

From `normalized_result.json` (failed run):

```json
[
  "python",
  "C:\\Users\\kaman\\Desktop\\pwmap\\runway_agent.py",
  "--job",
  "C:\\Users\\kaman\\Desktop\\pwmap\\agent_inbox\\job.json"
]
```

**Resolved shell equivalent:**

```text
python C:\Users\kaman\Desktop\pwmap\runway_agent.py --job C:\Users\kaman\Desktop\pwmap\agent_inbox\job.json
```

**Working directory:** `C:\Users\kaman\Desktop\pwmap`  
**Built by:** `content_brain/execution/pwmap_runway_agent_adapter.py` → `build_subprocess_command()`  
**Python selector:** `os.environ.get("PYTHON", "python")` — bare `python` on PATH, not `sys.executable`.

---

## 2. Captured I/O

### Run: `pwmap_20260623T204859_324bf879`

| Artifact | Present | Notes |
|----------|---------|-------|
| `subprocess_stdout.log` | **No** | Empty stdout — process died on import |
| `subprocess_stderr.log` | **Yes** | 223 bytes |
| `job.json` | **Yes** | Valid 2-clip multi prompt job |
| `normalized_result.json` | **Yes** | Full failure payload + preflight snapshot |
| `execution_report.json` | **No** | Not written by adapter |
| `agent_result.json` | **No** | Not written (agent never started) |
| `error.json` | **No** | Not written by adapter |
| `last_result.json` | **No** | pwmap never reached generation |
| `video.mp4` | **No** | — |

### stderr (complete)

```text
Traceback (most recent call last):
  File "C:\Users\kaman\Desktop\pwmap\runway_agent.py", line 28, in <module>
    from playwright.sync_api import Page, sync_playwright
ModuleNotFoundError: No module named 'playwright'
```

### stdout

Empty (no log file created).

### normalized_result.json (key fields)

```json
{
  "ok": false,
  "status": "failed",
  "subprocess_exit_code": 1,
  "message": "pwmap agent failed with exit code 1",
  "errors": ["pwmap_exit_code:1"],
  "pwmap_root": "C:/Users/kaman/Desktop/pwmap"
}
```

---

## 3. Environment Verification

### Python installations on host

| Interpreter | Version | `playwright` |
|-------------|---------|--------------|
| `C:\Python314\python.exe` | 3.14.5 | **Installed** |
| `C:\Users\kaman\AppData\Local\Programs\Python\Python311\python.exe` | 3.11.9 | **Missing** |
| WindowsApps stub | — | Not usable |

### Subprocess resolution (reproduced)

When the **parent process is Python 3.11** (typical ModirAgentOS API server):

```text
subprocess: python -c "import sys; print(sys.executable)"
→ C:\Users\kaman\AppData\Local\Programs\Python\Python311\python.exe
```

When the **parent process is Python 3.14** (terminal smoke test):

```text
subprocess: python -c "import sys; print(sys.executable)"
→ C:\Python314\python.exe
```

Re-running the exact failing command from a **3.11 parent** reproduces exit code 1 with the same `playwright` traceback.

### Environment variables (adapter-relevant, no secrets)

| Variable | Value at failure |
|----------|------------------|
| `PYTHON` | **Not set** → defaults to `"python"` |
| `MODIR_PWMAP_ROOT` | Not set → `C:\Users\kaman\Desktop\pwmap` |
| `PYTHONUNBUFFERED` | Not set by adapter (only set in `n8n_run.ps1`) |
| Subprocess `env` | Inherited from parent API process (no custom env in adapter) |
| Subprocess `cwd` | `C:\Users\kaman\Desktop\pwmap` |

### pwmap dependencies

`C:\Users\kaman\Desktop\pwmap\requirements.txt`:

```text
playwright>=1.40.0
```

No pwmap virtual environment (`.venv`) exists under the pwmap project.

### Paths & permissions

| Path | Status |
|------|--------|
| `C:\Users\kaman\Desktop\pwmap\agent_inbox\job.json` | Exists, writable (5189 bytes at failure time) |
| `C:\Users\kaman\Desktop\pwmap\runway_agent.py` | Exists |
| `C:\Users\kaman\Desktop\ModirAgentOS\outputs\pwmap_agent_runs\pwmap_20260623T204859_324bf879\` | Created, writable |
| File permissions | No access-denied errors in logs |

**Conclusion:** Paths and permissions are fine. The job JSON was written correctly before subprocess launch.

---

## 4. Failed Job Context (orchestration was correct)

The failed run was a **30s / 2-clip** Product Studio execution:

```json
{
  "model": "Kling 3.0 Pro",
  "duration": 15,
  "aspect": "9:16",
  "native_audio": true,
  "prompts": ["...", "..."],
  "use_frame_second": 14
}
```

Preflight snapshot confirms:

- `multiclip_execution_plan.clip_count`: 2
- `execution_mode`: `use_frame_chain`
- `duration_seconds`: 30

Orchestration completed planning and job build; failure occurred **before** browser automation started.

---

## 5. Success vs Failure Comparison

| Run | Time | Trigger | Parent Python | Subprocess `python` | Result |
|-----|------|---------|---------------|---------------------|--------|
| `pwmap_20260623T200804_256fb07a` | 22:08–22:24 | Live smoke script (terminal) | 3.14 | 3.14 | **SUCCESS** — 36 MB MP4 |
| `pwmap_20260623T204719_a0256aad` | 22:47 | Product Studio UI | 3.11 (inferred) | 3.11 | **FAIL** — import error |
| `pwmap_20260623T204859_324bf879` | 22:48 | Product Studio UI | 3.11 (inferred) | 3.11 | **FAIL** — import error |

The successful smoke run reached Runway browser steps (`subprocess_stdout.log` shows model selection, duration 15s, Generate clicked). Failed runs never passed the import line.

---

## 6. Root Cause

**Primary:** The pwmap adapter invokes `python` (bare name) instead of a pinned interpreter. When ModirAgentOS API runs under **Python 3.11**, Windows resolves subprocess `python` to **Python 3.11**, which lacks the `playwright` package required by `runway_agent.py`.

**Secondary:** `playwright` is installed on Python 3.14 (used for terminal smoke tests) but not on Python 3.11 (likely used by the Product Studio API server).

**Not the cause:**

- Product Studio duration planner
- Multi-clip routing / `use_frame_chain` job shape
- Use Frame implementation
- Browser automation mappings
- File permissions or job.json content

---

## 7. Minimal Safe Fix

**No Product Studio architecture changes required.** Pick one:

### Option A — Recommended (zero code change)

Set `PYTHON` before starting the ModirAgentOS API server to the interpreter that already has pwmap deps:

```powershell
$env:PYTHON = "C:\Python314\python.exe"
python -m uvicorn ui.api.main:app --host 127.0.0.1 --port 8000
```

The adapter already reads `os.environ.get("PYTHON", "python")`.

### Option B — Install deps on API Python

If the API must stay on 3.11:

```powershell
C:\Users\kaman\AppData\Local\Programs\Python\Python311\python.exe -m pip install -r C:\Users\kaman\Desktop\pwmap\requirements.txt
C:\Users\kaman\AppData\Local\Programs\Python\Python311\python.exe -m playwright install
```

### Option C — Future hardening (adapter-only, optional)

Add `MODIR_PWMAP_PYTHON` with fallback chain — outside this forensic scope; not required if Option A or B is applied.

### Verification after fix

```powershell
# From the same shell/session used to start the API:
python -c "import playwright; print('ok')"
python C:\Users\kaman\Desktop\pwmap\runway_agent.py --help
```

Then re-run a 30s Create Video generate from Product Studio.

---

## 8. Product Studio Architecture — Unchanged

This forensic phase made **no modifications** to:

- Product Studio service / UI
- Duration planner
- Multi-clip orchestration
- Use Frame chain
- Browser automation
- pwmap `runway_agent.py`

The failure is isolated to **subprocess Python environment selection** at the existing pwmap adapter boundary.

---

## Appendix: Run Folder Inventory

```
outputs/pwmap_agent_runs/pwmap_20260623T204859_324bf879/
├── job.json                  (5189 B)
├── normalized_result.json    (116389 B)
└── subprocess_stderr.log     (223 B)
```

```
outputs/pwmap_agent_runs/pwmap_20260623T200804_256fb07a/   [SUCCESS]
├── clip_1.mp4
├── job.json
├── last_result.json
├── normalized_result.json
├── subprocess_stdout.log
└── video.mp4
```
