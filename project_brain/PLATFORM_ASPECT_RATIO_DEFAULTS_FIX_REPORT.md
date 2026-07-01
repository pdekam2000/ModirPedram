# Platform Aspect Ratio Defaults Fix — Report

**Phase:** CRITICAL-FIX — ISSUE 2  
**Date:** 2026-06-03

---

## Problem

Product Studio showed incorrect defaults:

- Platform: **YouTube Shorts**
- Aspect: **16:9** (wrong — Shorts must be vertical)

---

## Required Defaults

| Platform | Aspect |
|----------|--------|
| TikTok | 9:16 |
| Instagram Reels | 9:16 |
| YouTube Shorts | 9:16 |
| YouTube Long | 16:9 |

When platform changes → aspect ratio auto-updates.

---

## Fix

### Backend

`content_brain/platform/platform_aspect_defaults.py`

- `default_aspect_ratio_for_platform()`
- `resolve_aspect_ratio()` — explicit override or platform default

Wired into `ProductStudioService.create_video_preflight()` → response includes `aspect_ratio`.

### Frontend

`ui/web/src/product/constants.ts`

- `PLATFORM_ASPECT_DEFAULTS`
- `defaultAspectRatioForPlatform()`
- Added **YouTube Long** platform option

`ui/web/src/pages/CreateVideoPage.tsx`

- `aspectRatio` state
- `useEffect` auto-updates aspect when platform changes
- Aspect ratio selector in Platform & Style section
- Preflight panel shows resolved aspect ratio
- `aspect_ratio` sent in preflight/generate payload

---

## Validation

```bash
python project_brain/validate_platform_aspect_ratio_defaults.py
```

Tests:

- Shorts → 9:16
- Reels → 9:16
- TikTok → 9:16
- Long YouTube → 16:9
- Preflight API returns correct aspect per platform
- UI constants + auto-update hook present

---

## Files Changed

| File | Change |
|------|--------|
| `content_brain/platform/platform_aspect_defaults.py` | **New** defaults module |
| `ui/api/product_studio_service.py` | Resolve + return `aspect_ratio` |
| `ui/web/src/product/constants.ts` | Defaults + YouTube Long |
| `ui/web/src/pages/CreateVideoPage.tsx` | Aspect UI + auto-update |
| `ui/web/src/api/productClient.ts` | Type includes `aspect_ratio` |
| `project_brain/validate_platform_aspect_ratio_defaults.py` | **New** validation suite |
