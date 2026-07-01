# PHASE YT-1 — YouTube Metadata Generator Report

**Phase:** `YT-1`  
**Date:** 2026-06-27  
**Scope:** Metadata generation only — no upload, OAuth, or YouTube API calls.

---

## Goal

Automatically generate publish-ready YouTube metadata from completed video packages in the Product Studio / Runway publish pipeline.

---

## Delivered

### New module

`content_brain/publish/youtube_metadata_generator.py`

Generates and stores `publish/youtube_metadata.json` with:

| Field | Purpose |
|-------|---------|
| `title` | CTR-optimized main title (spam patterns filtered) |
| `short_title` | Compact title for Shorts |
| `description` | Summary, hook, AI disclosure (if configured), CTA, hashtags |
| `tags` | Topic, genre, platform, AI video tags |
| `hashtags` | 3–10 deduplicated hashtags |
| `category` | YouTube category from niche mapping |
| `language` | ISO-style code (default `en`) |
| `made_for_kids` | From channel profile |
| `thumbnail_prompt` | Image-generation-ready thumbnail brief |
| `cta_text` | Subscribe/comment CTA |
| `seo_keywords` | Consolidated SEO terms |
| `publish_summary` | Human-readable publish readiness note |

### Integration points

| Location | Behavior |
|----------|----------|
| `runway_live_post_processor.run_publish_package()` | Writes `youtube_metadata.json` into Runway publish package |
| `product_multiclip_orchestrator` | Creates `run_dir/publish/` + metadata after successful Product Studio generation |
| `results_run_loader` | Exposes metadata fields on Results API |
| `product_studio_service._merge_pwmap_results()` | Loads metadata from pwmap run publish folder |
| `pwmap_finalization.build_pwmap_results_payload()` | Includes metadata in pwmap results payload |
| `ResultsPage.tsx` | Read-only YouTube Metadata panel |

### Not implemented (by design — PHASE YT-2)

- YouTube OAuth
- Video upload
- Scheduling
- Thumbnail rendering runtime
- Privacy setting application via API

---

## Format support

| Duration | `video_format` | Behavior |
|----------|----------------|----------|
| ≤ 60s or `youtube_shorts` target | `shorts` | Shorts-oriented title, vertical thumbnail prompt |
| > 60s | `long` | Long-form description, 16:9 thumbnail prompt |

---

## Storage layout

```
publish/
  youtube_metadata.json   ← primary deliverable
  metadata.json           ← package index (Product Studio runs)
  FINAL_*_VIDEO.mp4       ← video artifact when available
```

---

## Channel profile hooks

- `youtube_made_for_kids`
- `youtube_default_hashtags`
- `ai_creation_disclosure_enabled` / `youtube_ai_disclosure_enabled`
- `ai_disclosure_text` / `youtube_ai_disclosure`
- `cta_text` / `youtube_cta_text`
- `youtube_category` (optional override)
- `upload_platforms` (Shorts vs long detection)

---

## Validation

```powershell
python project_brain\validate_youtube_metadata_generator.py
```

Tests cover:

- Title, description, tags, hashtags, thumbnail prompt generation
- Hashtag count (3–10) and deduplication
- Metadata persisted under `publish/youtube_metadata.json`
- Shorts and long-form format detection
- Static + runtime guard against YouTube API calls
- Runway and Product Studio publish package wiring
- Full required schema fields

---

## Results UI

When metadata exists, Results shows:

- Title
- Category
- Tags count
- Hashtags
- Thumbnail prompt preview (truncated)

No editing UI in this phase.

---

## Next phase

**PHASE YT-2 — YouTube Upload Runtime**

- OAuth credential flow
- Upload API integration
- Scheduling
- Thumbnail upload
- Privacy settings application
