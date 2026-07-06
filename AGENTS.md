# AGENTS.md

## Cursor Cloud specific instructions

ModirAgentOS ships three front-ends over one codebase:

| Service | Path / entrypoint | Port | Notes |
| --- | --- | --- | --- |
| Dev-agent CLI | `python main.py` | — | Interactive text menu (project scan, handoff, orchestrator agents). Self-development toolchain; does NOT import the media pipeline. Works standalone. |
| Web API (backend) | `uvicorn ui.api.main:app --host 127.0.0.1 --port 8765` (or `python ui/api/main.py`) | 8765 | FastAPI control plane for the media-studio product. See known blocker below. |
| Web UI (frontend) | `npm run dev` in `ui/web` (Vite) | 5173 | React 18 + Vite + TS SPA. Talks to the API at `http://127.0.0.1:8765`. |

### Python environment
- Deps live in a project-local venv at `.venv` (Python 3.12). Activate with `. .venv/bin/activate` before running any Python entrypoint, or call `.venv/bin/python` directly. The update script keeps `.venv` refreshed from `requirements.txt` + `requirements-web.txt`.
- `ffmpeg` is available system-wide; `moviepy`/`imageio-ffmpeg` use it. Real media/voice/upload actions are gated behind explicit approval env flags (e.g. `MODIR_ASSEMBLY_REAL_EXECUTION_ENABLED`, `MODIR_VOICE_LIVE_TTS_ENABLED`) and external API keys loaded from a gitignored `.env` (`OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, Runway/Kling/etc.). Without keys the pipeline runs in dry-run/mock mode.

### Frontend
- Use `npm run dev` (Vite dev server) for development — Vite does not type-check, so it runs fine.
- `npm run build` currently FAILS on pre-existing TypeScript errors in `src/pages/ResultsPage.tsx` (properties missing on a response type). This is a pre-existing code issue, not an environment problem; prefer dev mode.
- `ui/web/node_modules` is committed to the repo but its `.bin/*` entries lose their executable bit / symlink nature on checkout (causing `tsc: Permission denied`). A fresh `npm install` (done by the update script) restores correct symlinks. Do not commit the resulting `node_modules` churn.

### KNOWN BLOCKER — backend cannot import (`content_brain.audio` missing)
- The FastAPI backend fails at import with `ModuleNotFoundError: No module named 'content_brain.audio'`.
- Root cause: the entire `content_brain/audio/` package (audio pipeline: `audio_post_processing`, `music_runtime`, `narration_engine`, `voice_casting_*`, `audio_merge_engine`, etc. — dozens of modules) was never committed. `.gitignore` line 53 has a broad `audio/` rule that matches `content_brain/audio/`, so the source is absent from the repo and from disk.
- Impact: the web backend (`ui/api/main.py`) and anything importing `content_brain.audio` (most of `content_brain/execution`, `story`, `quality`, `platform`, and `project_brain/validate_*` scripts) cannot run until that source is restored. The CLI (`main.py`) and the frontend dev server are unaffected.
- To unblock the backend, the missing `content_brain/audio/` source must be restored (e.g. force-add it past the gitignore, or narrow the `.gitignore` `audio/` rule so it only targets generated media dirs, then commit the package). Do not fabricate these modules.
