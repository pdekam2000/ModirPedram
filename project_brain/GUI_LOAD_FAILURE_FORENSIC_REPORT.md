# GUI Load Failure — Forensic Report

**Investigation:** PRODUCT STUDIO GUI FAILED TO LOAD  
**Date:** 2026-06-18  
**Status:** Investigation only — no fixes applied

---

## 1. Root Cause

**Primary (confirmed, reproducible):** Backend **schema/type mismatch** in the Kling Frame-to-Video preflight path. `collect_kling_preflight_warnings()` assumes every clip has multishot fields `shot_1` and `shot_2`, but the primary production path now passes `KlingFrameToVideoClipPlan` clips (single rich `prompt` per clip, no `shot_1`/`shot_2`). This raises `AttributeError` and returns **HTTP 500** on Kling preflight and generate, breaking Create Video for Kling Native Audio / Frame-to-Video.

**Contributing (observed in Vite dev logs, currently resolved):** A transient **frontend transform failure** in `ui/web/src/api/productClient.ts` (`esbuild`: `Expected "}" but found ";"` at line 247) caused Vite **Internal server error** and would block the entire SPA module graph until HMR recovered. `npx vite build` **passes today**.

---

## 2. Evidence

### 2.1 Backend status

| Check | Result | Evidence |
|-------|--------|----------|
| FastAPI process running | **YES** | Terminal `2.txt`: active command `python -m uvicorn ui.api.main:app --host 0.0.0.0 --port 8765 --reload` |
| Correct port | **YES** | `8765` |
| Startup import exceptions | **NO** | `python -c "import ui.api.main"` → `import ok` |
| Missing route registration | **NO** | Routes present in `ui/api/main.py` |
| `GET /health` | **200** | `{"status":"ok","service":"modiragent-api","version":"0.6.0"}` |

### 2.2 Backend failure (Kling path) — exact traceback

**Request:** `POST /product/create-video/generate`  
**Response:** `500 Internal Server Error`

```
File "C:\Users\kaman\Desktop\ModirAgentOS\ui\api\main.py", line 1005, in product_create_video_generate
    result = service.create_video_generate(payload, runway_service=runway_service)
File "C:\Users\kaman\Desktop\ModirAgentOS\ui\api\product_studio_service.py", line 905, in create_video_generate
    preflight = self.create_video_preflight(payload)
File "C:\Users\kaman\Desktop\ModirAgentOS\ui\api\product_studio_service.py", line 494, in create_video_preflight
    collect_kling_preflight_warnings(
File "C:\Users\kaman\Desktop\ModirAgentOS\content_brain\execution\kling_native_audio_planner.py", line 692, in collect_kling_preflight_warnings
    for shot_name, shot in (("shot_1", clip.shot_1), ("shot_2", clip.shot_2)):
                                       ^^^^^^^^^^^
AttributeError: 'KlingFrameToVideoClipPlan' object has no attribute 'shot_1'
```

**Reproduced via API:**

```
POST http://127.0.0.1:8765/product/create-video/preflight
Body: {"topic":"young boy and baby dragon neon city","duration_seconds":30,"platform":"youtube","provider":"kling","audio_strategy":"kling_native_audio"}
→ STATUS 500 Internal Server Error
```

Same traceback logged for `product_create_video_preflight` at `main.py` line 994.

**Non-Kling preflight still works:**

```
POST /product/create-video/preflight (generic topic, runway route)
→ STATUS 200
```

### 2.3 Call chain introducing mismatch (Kling Frame integration)

`ui/api/product_studio_service.py` `create_video_preflight()` when `kling_preflight_active`:

1. Line 460: `kling_plan = plan_kling_frame_from_audio_route(...)` → returns `KlingFrameToVideoPlan`
2. Line 494–500: `collect_kling_preflight_warnings(plan=kling_plan, ...)` — passes frame plan to multishot-oriented warning collector

Introduced by **KLING-FRAME-TO-VIDEO** / **USE-FRAME-CONTINUITY** primary path switch. `collect_kling_preflight_warnings` was not updated for `KlingFrameToVideoClipPlan`.

### 2.4 Frontend status

| Check | Result | Evidence |
|-------|--------|----------|
| Vite running | **YES** | Terminal `1.txt`: active command `npm run dev` |
| Vite port | **5173** | `ui/web/vite.config.ts` `server.port: 5173` |
| `npx vite build` | **PASS** | `✓ 101 modules transformed`, built in 750ms |
| `npm run build` (tsc + vite) | **FAIL** | Unrelated TS errors in `RunwayBrowserPanel.tsx`, `UploadCenterPage.tsx` |

### 2.5 Frontend dev-server error (exact message)

From Vite terminal `1.txt` at `22:59:24`:

```
[vite] Internal server error: Transform failed with 1 error:
C:/Users/kaman/Desktop/ModirAgentOS/ui/web/src/api/productClient.ts:247:18: ERROR: Expected "}" but found ";"
  Plugin: vite:esbuild
  File: C:/Users/kaman/Desktop/ModirAgentOS/ui/web/src/api/productClient.ts:247:18

  Expected "}" but found ";"
  245|    const query = params.toString() ? `?${params.toString()}` : "";
  246|    return request<{
  247|      found: boolean;
     |                    ^
  248|      video_path: string;
```

Later HMR updates to `productClient.ts` / `ResultsPage.tsx` succeeded (`03:55:38`, `18:49:46`, `10:43:47`).

### 2.6 API connectivity

| Setting | Value |
|---------|-------|
| Frontend URL | `http://127.0.0.1:5173` |
| Backend URL | `http://127.0.0.1:8765` |
| `ui/web/.env` | `VITE_API_BASE_URL=http://127.0.0.1:8765` |
| `ui/web/src/config/apiConfig.ts` | `DEFAULT_API_BASE_URL = "http://127.0.0.1:8765"` |

**Note:** `GET /product/preflight` does **not** exist → **404**. Correct endpoint is `POST /product/create-video/preflight` → **405** on GET.

### 2.7 GUI partially loaded (contradicts total failure)

Terminal `2.txt` shows successful requests while GUI was in use:

```
GET /platform/auth/me → 200
GET /product/channel-profile → 200
GET /product/results/latest → 200
POST /product/create-video/generate → 500
```

Auth, channel profile, and Results API work. Failure is **route-specific** on Kling Create Video preflight/generate, not universal API outage.

### 2.8 Recent phase impact audit

| Phase | Impact on GUI load |
|-------|-------------------|
| KLING-FRAME-TO-VIDEO | **YES** — frame plan passed to multishot `collect_kling_preflight_warnings` → 500 |
| USE-FRAME-CONTINUITY | Indirect (same preflight path) |
| STORY-PROGRESSION-ENGINE | No crash; adds `story_progression` to preflight JSON |
| VIDEO-JUDGE-P1 | Frontend type additions in `productClient.ts`; correlated with transient esbuild error in dev log; **current build passes** |

No Pydantic response-model serialization failure observed. Failure occurs **before** response construction (unhandled exception).

---

## 3. Exact Failing File

**Backend (primary):** `content_brain/execution/kling_native_audio_planner.py`  
**Exact line:** **692**  
**Caller:** `ui/api/product_studio_service.py` line **494**

**Frontend (contributing, transient):** `ui/web/src/api/productClient.ts`  
**Exact line:** **247** (per Vite/esbuild log)

---

## 4. Failure Category

| Layer | Caused failure? |
|-------|-----------------|
| Backend process down | No |
| Frontend dev server down | No |
| API connectivity / wrong URL | No |
| **Backend schema / type mismatch** | **Yes (primary)** |
| **Frontend transform / syntax (transient)** | **Possible full-SPA blocker during dev session** |
| Routing registration | No |
| JSON serialization | No |

---

## 5. Fix Recommendation (do not implement yet)

1. **Backend:** Update `collect_kling_preflight_warnings()` to accept `KlingFrameToVideoPlan` / `KlingFrameToVideoClipPlan` and validate `clip.prompt` length instead of `clip.shot_1` / `clip.shot_2`. Alternatively, pass `plan_kling_from_audio_route(...)` (multishot plan) only to the warning collector while keeping frame plan as primary in preflight payload.

2. **Integration test:** `POST /product/create-video/preflight` with `provider=kling` + `audio_strategy=kling_native_audio` must return 200.

3. **Frontend:** Confirm `productClient.ts` generic type block at line 246+ remains valid; run `npm run dev` clean restart if esbuild error reappears. Resolve unrelated `tsc` errors in `RunwayBrowserPanel.tsx` and `UploadCenterPage.tsx` for production builds.

---

## 6. Risk Assessment

| Risk | Level | Notes |
|------|-------|-------|
| Kling Create Video completely blocked | **High** | Every preflight/generate hits line 692 |
| Full SPA white screen | **Medium (transient)** | Historical `productClient.ts` esbuild error; not present in current `vite build` |
| Results / Settings pages | **Low** | `GET /product/results/latest` returns 200 |
| Production deploy | **Medium** | `npm run build` fails `tsc` on unrelated files |
| Data loss | **None** | No writes before exception |

---

## 7. API Test Summary

```
GET  /health                              → 200 {"status":"ok","service":"modiragent-api","version":"0.6.0"}
GET  /product/preflight                   → 404 Not Found
GET  /product/create-video/preflight      → 405 Method Not Allowed
POST /product/create-video/preflight      → 200 (runway/generic topic)
POST /product/create-video/preflight      → 500 (kling + kling_native_audio) AttributeError shot_1
POST /product/create-video/generate       → 500 (same AttributeError, terminal evidence)
GET  /product/results/latest              → 200 (terminal evidence)
```

---

## 8. Conclusion

The Product Studio GUI **shell loads** (auth, channel profile, results). **Kling Frame-to-Video Create Video is broken** by a backend `AttributeError` at `kling_native_audio_planner.py:692` when frame clip plans are passed to a multishot-only warning function. A **transient frontend esbuild error** in `productClient.ts:247` was also observed and would have caused a full dev-server module transform failure during recent VIDEO-JUDGE-P1 / Results type edits; that error is **not present** in the current successful `vite build`.
