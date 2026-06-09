# Topic Universe / SEO Title Bank Agent — Report

## Summary

Content Brain now includes a **Topic Universe / SEO Title Bank** planning layer that expands broad categories (e.g. `fishing`) into many specific, deduplicated, SEO-ready video titles before any story or Runway work begins.

Specific instructional topics (e.g. `zander fishing method`) bypass the title bank and return a **single focused video plan** for direct E2E pipeline use.

---

## Files Created

| File | Purpose |
|------|---------|
| `content_brain/execution/topic_universe_builder.py` | Core scope detection, seed expansion, dedup, topic authority, metadata |
| `content_brain/execution/topic_universe_studio.py` | Studio orchestrator, trend integration, JSON/MD/CSV export |
| `ui/api/topic_universe_studio_service.py` | API service + E2E handoff |
| `ui/api/schemas/topic_universe_studio.py` | Pydantic request/response schemas |
| `ui/web/src/api/topicUniverseClient.ts` | Frontend API client |
| `ui/web/src/pages/TopicUniverseStudioPage.tsx` | Operator UI (title table, copy, E2E handoff) |
| `project_brain/validate_topic_universe_title_bank.py` | Validation suite (15 checks) |
| `project_brain/topic_universe_results/` | Export directory (`latest.json`, `latest.md`, `latest.csv`) |

## Files Modified

| File | Change |
|------|--------|
| `ui/api/main.py` | Routes: `/topic-universe-studio/preflight`, `/generate`, `/handoff-e2e`, `/open-export`, `/status` |
| `ui/web/src/pages/ExecutionCenterPage.tsx` | New tab: **Topic Universe Studio** |
| `ui/web/src/App.css` | Title table + checkbox form styles |

---

## Architecture

```
User Topic
    ↓
Language Detection
    ↓
Broad vs Specific Scope Detection
    ↓
┌───────────────────────────────┬──────────────────────────────┐
│ BROAD (fishing, pizza)        │ SPECIFIC (zander fishing     │
│                               │ method, how to make dough)   │
│ Trend Discovery (optional)    │                              │
│ Seed Subcategory Expansion    │ Single Video Plan Entry      │
│ Title Metadata + Dedup        │                              │
│ SEO Title Bank (target 100)   │                              │
└───────────────────────────────┴──────────────────────────────┘
    ↓
Export JSON / Markdown / CSV
    ↓
Operator selects one title
    ↓
Content Brain E2E Micro Test (story, clips, prompts, SEO)
```

### Broad vs Specific Detection

| Input | Scope | Output mode |
|-------|-------|-------------|
| `fishing` | broad | ~100 title bank |
| `pizza` | broad | title bank (generic seed templates) |
| `zander fishing` | semi_specific | narrowed bank (species-focused) |
| `zander fishing method` | specific | 1 video plan |
| `how to make pizza dough` | specific | 1 video plan |

Rules use:

- Raw word count
- Instructional intent markers (`method`, `how to`, `tutorial`, …)
- Domain hints from `content_brain_topic_authority`
- Species/sub-niche narrowing for fishing (`zander`, `pike`, …)

---

## Provider Usage

When **Use live trends** is enabled:

1. `TrendDiscoveryEngine` queries configured providers (DataForSEO, SerpAPI, etc.)
2. Trend opportunities are merged into the title bank with higher `trend_score`
3. `trend_mode` reflects live sources via `classify_trend_sources()`

When APIs are unavailable:

- `trend_mode = fallback_seed_expansion`
- Notes explicitly state fallback mode
- Structured fishing/generic seed templates still produce a full bank

OpenAI is **not required** for title bank generation. OpenAI story enrichment remains in the E2E handoff step only.

---

## Deduplication Strategy

1. **Exact duplicate removal** — normalized lowercase + punctuation-stripped titles
2. **Bad generic filter** — rejects titles like `fishing tips`, `best fishing`, `how to fishing`
3. **Near-duplicate detection** — Jaccard word overlap ≥ 0.82
4. **Template repeat cap** — max 2 titles per skeleton pattern
5. **Subtopic cap** — max 8 titles per subcategory for diversity

Each title includes `duplicate_status`: `unique`, `exact_duplicate`, `near_duplicate`, `template_repeat`, or `subtopic_cap` (rejected entries are not exported).

---

## Topic Authority

Every title must pass `title_passes_topic_authority()`:

- Broad `fishing` → must contain fishing-related terms
- Semi-specific `zander fishing` → must mention `zander`
- Specific topics → single plan anchored to user input
- Unrelated domains (e.g. pizza in a fishing bank) are rejected

---

## Title Metadata (per entry)

- `title`, `subtopic`, `category`, `intent`, `difficulty`
- `estimated_viral_potential`, `educational_value`, `trend_score`
- `source_provider`, `keywords`
- `suggested_duration`, `suggested_clip_count`, `content_strategy`
- `duplicate_status`

---

## Sample Output — `fishing`

Offline run (`use_live_trends=false`, target 100):

- **Scope:** broad
- **Mode:** title_bank
- **Trend mode:** fallback_seed_expansion
- **Titles generated:** 95 unique (5 filtered by dedup/quality rules)
- **Subtopics:** 20 (beginner tips, lure fishing, zander, knots, night fishing, …)

Example titles:

1. 7 Fishing Mistakes Beginners Make Without Realizing
2. The Best Lure Color for Murky Water Fishing
3. How to Catch Zander in Shallow Water at Night
4. Why Your Fishing Line Keeps Breaking at the Knot
5. How to Set the Hook Properly Every Time
6. The Simple Knot Every Beginner Angler Should Learn
7. How to Find Fish Fast in a New Lake
8. The Biggest Mistake When Using Soft Plastic Lures
9. How to Fish Deep Water Without Losing Your Lure
10. Can You Catch a Fish With Only One Lure All Day?

---

## Validation Results

```text
python project_brain/validate_topic_universe_title_bank.py
```

All 15 requirement checks **PASS**:

1. Broad `fishing` generates fishing-related titles
2. 100 titles attempted (95 kept after quality/dedup)
3. Titles are unique
4. No unrelated topics
5. Subcategories present (20)
6. Intent labels present
7. Duplicate detection works
8. `zander fishing method` → specific single plan (not broad bank)
9. JSON export works
10. Markdown export works
11. CSV export works
12. UI route + page exist
13. Selected title handoff → Content Brain E2E completes
14. Live trend mode supported when configured
15. Fallback seed expansion clearly labeled

---

## How to Use in the UI

1. Open **Execution Center → Topic Universe Studio**
2. Enter a broad topic (e.g. `fishing`)
3. Set title count target (default 100), platform, audience level
4. Toggle **Use live trends** if DataForSEO/SerpAPI are configured
5. Click **Generate Title Bank**
6. Browse/filter the title table by subtopic
7. **Copy** a title or click **E2E** / **Send Selected Title to E2E Test**
8. E2E pipeline runs: trends → classification → story → clips → prompts (no Runway)
9. Use **Open Export Folder** for `project_brain/topic_universe_results/latest.json`

### Workflow

```
fishing → 100 SEO titles → pick one → Content Brain E2E → Runway prompts → (later) media
```

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/topic-universe-studio/preflight` | Provider readiness |
| POST | `/topic-universe-studio/generate` | Generate title bank |
| POST | `/topic-universe-studio/handoff-e2e` | Run E2E with selected title |
| POST | `/topic-universe-studio/open-export` | Open export folder |
| GET | `/topic-universe-studio/status` | Last run status |

---

## Notes

- No Runway, image, or video generation in this phase
- Restart API after backend changes: `python -m ui.api.main`
- Export paths: `project_brain/topic_universe_results/latest.{json,md,csv}`
