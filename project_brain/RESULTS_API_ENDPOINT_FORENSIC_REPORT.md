# RESULTS API ENDPOINT FORENSIC REPORT

**Phase:** RESULTS-API-ENDPOINT-FORENSIC  
**Date:** 2026-06-28  
**Symptom:** Results page shows **Failed to fetch**  
**Manual probe:** `GET /results` → **404 Not Found** (expected — route does not exist)

---

## Executive Summary

| Item | Finding |
|------|---------|
| **Correct endpoint** | `GET /product/results/latest` |
| **Frontend URL** | `http://127.0.0.1:8765/product/results/latest` |
| **Wrong URL tested** | `/results` — never registered |
| **Root cause** | **500 Internal Server Error** — Pydantic validation failure on `branding_status` |
| **Not the cause** | Wrong endpoint in frontend, CORS, port mismatch, stale API |

The browser shows "Failed to fetch" because the API returns **500** (not 404). CORS preflight succeeds; the response body never validates.

---

## 1. Frontend Inspection

### ResultsPage.tsx

- Loads via `fetchLatestResults(runId)` on mount (`useEffect` → `loadResults("")`)
- Error banner: `{error && <div className="error-banner">{error}</div>}` — displays fetch exception message

### productClient.ts — `fetchLatestResults`

```typescript
return request(`/product/results/latest${query}`);
```

Query params (optional): `run_id`, `run_dir`

### API base URL

| Source | Value |
|--------|-------|
| `ui/web/src/config/apiConfig.ts` | Default `http://127.0.0.1:8765` |
| `ui/web/.env` | `VITE_API_BASE_URL=http://127.0.0.1:8765` |

**Full failing URL:** `http://127.0.0.1:8765/product/results/latest`

---

## 2. Backend Routes (Results-related)

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| **GET** | **`/product/results/latest`** | `product_latest_results` | **Primary Results page data** |
| GET | `/upload/youtube/result` | `upload_youtube_result` | YouTube upload result by run_id |
| GET | `/upload/youtube/auth/result` | `upload_youtube_auth_result` | OAuth status |
| GET | `/health` | `health` | API health + build diagnostics |
| GET | `/platform/runtime-diagnostics` | `platform_runtime_diagnostics` | Stale-server detection |

**No route exists for:** `/results`, `/api/results`, `/product/results` (without `/latest`)

### Endpoint implementation

```python
@app.get("/product/results/latest", response_model=LatestResultsResponse)
def product_latest_results(run_id: str = "", run_dir: str = "", service=Depends(...)):
    return LatestResultsResponse(**service.get_results(run_id=run_id, run_dir=run_dir))
```

Service path: `ProductStudioService.get_results()` → `_merge_pwmap_results()` for latest pwmap run.

---

## 3. Live Request Verification

### `/health` — OK

```
api_process_stale: false
orchestrator_version: product_multiclip_orchestrator_v3
assembly_bridge_enabled / branding_publish_enabled / youtube_metadata_enabled / auto_upload_enabled: true
```

### `GET /product/results/latest` — **500 Internal Server Error**

**Terminal traceback (ui.api.main):**

```
File "ui/api/main.py", line 1169, in product_latest_results
  return LatestResultsResponse(**service.get_results(...))
pydantic_core.ValidationError: 1 validation error for LatestResultsResponse
branding_status
  Input should be a valid dictionary or instance of BrandingStatusDTO
  [type=model_type, input_value='', input_type=str]
```

**HTTP log:**

```
INFO: "GET /product/results/latest HTTP/1.1" 500 Internal Server Error
```

**CORS:** Not blocked — request reaches handler; failure is post-handler validation.

---

## 4. Root Cause Analysis

### Primary: Response schema mismatch (introduced in publish-chain merge)

`LatestResultsResponse.branding_status` is typed as **`BrandingStatusDTO`** (object):

```python
class BrandingStatusDTO(BaseModel):
    status: str = ""
    branding_enabled: bool = False
    final_branded_video_path: str = ""
    ...
```

`_merge_pwmap_results()` was setting:

```python
"branding_status": str(...)  # e.g. "completed" or ""
```

FastAPI/Pydantic rejects the string → **500** → frontend `fetch` throws → **"Failed to fetch"**.

### Secondary confusion: `/results` vs `/product/results/latest`

Manual check of `/results` returning 404 is **expected** and unrelated to the Results page, which never calls that path.

### Ruled out

| Hypothesis | Verdict |
|------------|---------|
| Frontend wrong endpoint | ❌ Uses correct `/product/results/latest` |
| CORS / base URL mismatch | ❌ Port 8765 matches; other endpoints work |
| Auto-upload fields crash service | ❌ Service builds payload OK; crash is at response_model validation |
| Stale API process | ❌ `/health` shows v3 orchestrator; error is deterministic schema bug |

---

## 5. Fix Applied

**File:** `ui/api/product_studio_service.py` — `_merge_pwmap_results()`

- `branding_status` now returns a **`BrandingStatusDTO`-compatible dict** (status, subtitles, logo, cta, etc.)
- Added `branding_publish_status: str` for flat publish-chain display

**File:** `ui/api/schemas/product_studio.py`

- Added `branding_publish_status: str = ""`

**File:** `ui/web/src/pages/ResultsPage.tsx`

- Publish section uses `branding_publish_status` / `branding?.status` instead of rendering object as string

### Post-fix validation (local Python, new code)

```bash
python -c "from ui.api.product_studio_service import ProductStudioService; ..."
# LatestResultsResponse(**payload) → OK
# found=True, auto_upload_enabled=True
```

**Operator action required:** Restart API server to load fix:

```bash
python -m ui.api.main
```

Then verify:

```bash
curl http://127.0.0.1:8765/product/results/latest
# Expect HTTP 200 + JSON with found, pipeline_trace, auto_upload_enabled, etc.
```

---

## 6. Expected Results Page After Restart

| Panel | Data source |
|-------|-------------|
| Canonical Run | `selected_run_id`, `run_dir`, `topic` |
| Publish Chain Trace | `pipeline_trace`, `api_build_id`, capability flags |
| YouTube Upload | `auto_upload_enabled`, `auto_upload_started`, `youtube_upload_status`, blocked reason |
| Assembly / Publish | `assembly_status`, `publish_status`, `branding_publish_status` |

---

## 7. Quick Reference

```
WRONG:  GET /results                          → 404
RIGHT:  GET /product/results/latest           → 200 (after fix + restart)
        GET /product/results/latest?run_id=…  → specific run
HEALTH: GET /health                           → 200
UPLOAD: GET /upload/youtube/result?run_id=…   → upload artifact
```

---

*End of report.*
