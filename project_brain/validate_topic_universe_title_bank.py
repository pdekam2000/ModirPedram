"""
Validate Topic Universe / SEO Title Bank agent.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.execution.topic_universe_builder import (
    build_title_bank,
    deduplicate_title_entries,
    detect_topic_scope,
    normalize_title,
    title_passes_topic_authority,
)
from content_brain.execution.topic_universe_studio import (
    DEFAULT_EXPORT_DIR,
    TopicUniverseStudio,
    run_topic_universe_studio,
)


def _pass(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def _fishing_terms() -> tuple[str, ...]:
    return (
        "fish",
        "fishing",
        "angler",
        "lure",
        "cast",
        "hook",
        "bait",
        "rod",
        "reel",
        "zander",
        "pike",
        "carp",
        "bass",
        "trout",
        "knot",
        "tide",
        "lake",
        "river",
        "sea",
        "bites",
    )


def test_broad_fishing_bank() -> None:
    payload = run_topic_universe_studio(
        topic="fishing",
        title_target=100,
        use_live_trends=False,
        platform="youtube_shorts",
    )
    _pass("fishing_run_completed", payload.get("status") == "completed")
    bank = payload.get("title_bank") or {}
    titles = list(bank.get("titles") or [])
    _pass("fishing_attempts_100", bank.get("title_target") == 100, str(bank.get("title_count")))
    _pass("fishing_has_many_titles", len(titles) >= 80, str(len(titles)))
    _pass("fishing_mode_title_bank", bank.get("mode") == "title_bank")
    _pass("fishing_scope_broad", (bank.get("scope") or {}).get("scope") == "broad")

    normalized = [normalize_title(str(item.get("title") or "")) for item in titles]
    _pass("fishing_unique_titles", len(normalized) == len(set(normalized)), str(len(set(normalized))))

    unrelated = [title for title in normalized if not any(term in title for term in _fishing_terms())]
    _pass("fishing_no_unrelated", len(unrelated) == 0, unrelated[:3])

    subtopics = {str(item.get("subtopic") or "") for item in titles}
    _pass("fishing_has_subtopics", len(subtopics) >= 10, str(len(subtopics)))

    intents = {str(item.get("intent") or "") for item in titles}
    _pass("fishing_has_intents", len(intents) >= 3, str(intents))

    _pass(
        "fishing_fallback_labeled",
        bank.get("trend_mode") == "fallback_seed_expansion"
        or "fallback_seed_expansion" in " ".join(bank.get("notes") or []),
        str(bank.get("trend_mode")),
    )


def test_specific_zander_method() -> None:
    payload = run_topic_universe_studio(topic="zander fishing method", use_live_trends=False, title_target=100)
    bank = payload.get("title_bank") or {}
    titles = list(bank.get("titles") or [])
    _pass("zander_method_specific_mode", bank.get("mode") == "specific_video_plan")
    _pass("zander_method_single_plan", len(titles) == 1)
    combined = normalize_title(str(titles[0].get("title") if titles else ""))
    _pass("zander_method_title_focused", "zander" in combined or "method" in combined, combined)


def test_deduplication() -> None:
    from content_brain.execution.topic_universe_builder import TitleBankEntry

    entries = [
        TitleBankEntry(
            title_id="a",
            title="How to Catch Zander in Shallow Water at Night",
            subtopic="zander fishing",
            category="fishing",
            intent="how_to",
            difficulty="intermediate",
            estimated_viral_potential=0.6,
            educational_value=0.8,
            trend_score=0.4,
            source_provider="seed_expansion",
            keywords=["zander"],
            suggested_duration=30,
            suggested_clip_count=3,
            content_strategy="instructional_fishing",
        ),
        TitleBankEntry(
            title_id="b",
            title="How to Catch Zander in Shallow Water at Night",
            subtopic="zander fishing",
            category="fishing",
            intent="how_to",
            difficulty="intermediate",
            estimated_viral_potential=0.6,
            educational_value=0.8,
            trend_score=0.4,
            source_provider="seed_expansion",
            keywords=["zander"],
            suggested_duration=30,
            suggested_clip_count=3,
            content_strategy="instructional_fishing",
        ),
    ]
    kept, stats = deduplicate_title_entries(entries, title_target=10)
    _pass("dedup_removes_exact", len(kept) == 1, str(stats))


def test_exports() -> None:
    studio = TopicUniverseStudio()
    result = studio.run({"topic": "fishing", "title_target": 20, "use_live_trends": False})
    _pass("export_run_completed", result.status == "completed")
    paths = result.export_paths
    _pass("export_json", bool(paths.get("json")))
    _pass("export_md", bool(paths.get("markdown")))
    _pass("export_csv", bool(paths.get("csv")))
    json_path = Path(paths["json"])
    md_path = Path(paths["markdown"])
    csv_path = Path(paths["csv"])
    _pass("export_json_exists", json_path.is_file())
    _pass("export_md_exists", md_path.is_file())
    _pass("export_csv_exists", csv_path.is_file())
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    _pass("export_json_has_titles", len(saved.get("title_bank", {}).get("titles") or []) >= 1)
    _pass("export_md_has_heading", "# Topic Universe" in md_path.read_text(encoding="utf-8"))
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    _pass("export_csv_has_rows", len(rows) >= 1)


def test_handoff_e2e() -> None:
    from ui.api.topic_universe_studio_service import TopicUniverseStudioService

    service = TopicUniverseStudioService()
    bank = service.generate({"topic": "fishing", "title_target": 5, "use_live_trends": False})
    titles = list((bank.get("result") or {}).get("title_bank", {}).get("titles") or [])
    _pass("handoff_bank_ready", len(titles) >= 1)
    selected = str(titles[0].get("title") or "")
    handoff = service.handoff_to_e2e(
        {
            "selected_title": selected,
            "source_run_id": (bank.get("result") or {}).get("run_id"),
            "duration_seconds": 30,
            "platform": "youtube_shorts",
            "niche": "general",
            "mood": "instructional",
        }
    )
    _pass("handoff_ok", handoff.get("ok") is True, handoff.get("message", ""))
    e2e = handoff.get("result") or {}
    _pass("handoff_e2e_completed", e2e.get("status") == "completed", str(e2e.get("status")))


def test_implementation_wiring() -> None:
    builder_src = (ROOT / "content_brain/execution/topic_universe_builder.py").read_text(encoding="utf-8")
    studio_src = (ROOT / "content_brain/execution/topic_universe_studio.py").read_text(encoding="utf-8")
    api_src = (ROOT / "ui/api/main.py").read_text(encoding="utf-8")
    page_src = (ROOT / "ui/web/src/pages/TopicUniverseStudioPage.tsx").read_text(encoding="utf-8")
    exec_src = (ROOT / "ui/web/src/pages/ExecutionCenterPage.tsx").read_text(encoding="utf-8")
    _pass("builder_module", "build_title_bank" in builder_src)
    _pass("scope_detection", "detect_topic_scope" in builder_src)
    _pass("dedup_logic", "deduplicate_title_entries" in builder_src)
    _pass("studio_module", "TopicUniverseStudio" in studio_src)
    _pass("export_dir", "topic_universe_results" in studio_src)
    _pass("generate_route", "/topic-universe-studio/generate" in api_src)
    _pass("handoff_route", "/topic-universe-studio/handoff-e2e" in api_src)
    _pass("ui_page", "TopicUniverseStudioPage" in page_src)
    _pass("execution_center_tab", "topic_universe" in exec_src)
    _pass("provider_support", "use_live_trends" in studio_src)
    _pass("topic_authority", "title_passes_topic_authority" in builder_src)


def test_topic_authority_filter() -> None:
    scope = detect_topic_scope("fishing")
    ok = title_passes_topic_authority("How to Catch Zander in Shallow Water at Night", "fishing", scope)
    bad = title_passes_topic_authority("Why Pizza Dough Fails in Hot Ovens", "fishing", scope)
    _pass("authority_accepts_fishing", ok)
    _pass("authority_rejects_unrelated", not bad)


def main() -> int:
    print("[validate_topic_universe_title_bank] Topic Universe / SEO Title Bank")
    test_implementation_wiring()
    test_topic_authority_filter()
    test_deduplication()
    test_broad_fishing_bank()
    test_specific_zander_method()
    test_exports()
    test_handoff_e2e()
    print(f"\nExport directory: {DEFAULT_EXPORT_DIR}")
    print("\n[validate_topic_universe_title_bank] All checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
