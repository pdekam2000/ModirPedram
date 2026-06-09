"""
Topic Universe Studio — orchestrates title bank generation, export, and E2E handoff.
"""

from __future__ import annotations

import csv
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPORT_DIR = ROOT / "project_brain" / "topic_universe_results"

from content_brain.engines.trend_discovery_engine import TrendDiscoveryEngine
from content_brain.execution.content_brain_studio_preflight import classify_trend_sources
from content_brain.execution.content_brain_topic_locale import detect_language_code, profile_with_output_language
from content_brain.execution.topic_universe_builder import (
    DEFAULT_TITLE_TARGET,
    TitleBankResult,
    build_title_bank,
    detect_topic_scope,
)
from content_brain.profiles.profile_loader import ProfileLoader
from content_brain.schemas.content_brief import Platform


def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 2)


@dataclass
class TopicUniverseInput:
    topic: str
    language_code: str | None = None
    platform: str = "youtube_shorts"
    audience_level: str = "general"
    niche_style: str = "general"
    title_target: int = DEFAULT_TITLE_TARGET
    use_live_trends: bool = True
    suggested_duration: int = 30


@dataclass
class TopicUniverseRunResult:
    run_id: str
    status: str
    started_at: str
    completed_at: str = ""
    total_duration_ms: float = 0.0
    input: dict[str, Any] = field(default_factory=dict)
    title_bank: dict[str, Any] = field(default_factory=dict)
    export_paths: dict[str, str] = field(default_factory=dict)
    e2e_handoff: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    studio_version: str = "topic_universe_studio_v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_ms": self.total_duration_ms,
            "input": dict(self.input),
            "title_bank": dict(self.title_bank),
            "export_paths": dict(self.export_paths),
            "e2e_handoff": dict(self.e2e_handoff),
            "errors": list(self.errors),
            "studio_version": self.studio_version,
        }


class TopicUniverseStudio:
    STUDIO_VERSION = "topic_universe_studio_v1"

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        export_dir: Path | None = None,
        trend_engine: TrendDiscoveryEngine | None = None,
        profile_loader: ProfileLoader | None = None,
    ) -> None:
        self.project_root = project_root or ROOT
        self.export_dir = export_dir or DEFAULT_EXPORT_DIR
        self.trend_engine = trend_engine or TrendDiscoveryEngine()
        self.profile_loader = profile_loader or ProfileLoader(project_root=self.project_root)

    def run(self, spec: TopicUniverseInput | dict[str, Any]) -> TopicUniverseRunResult:
        payload = self._coerce_input(spec)
        started = time.perf_counter()
        run_id = f"topic_universe_{uuid.uuid4().hex[:12]}"
        language_code = payload.language_code or detect_language_code(payload.topic)
        scope = detect_topic_scope(payload.topic, language_code=language_code)

        result = TopicUniverseRunResult(
            run_id=run_id,
            status="running",
            started_at=_now_stamp(),
            input={
                "topic": payload.topic,
                "language_code": language_code,
                "platform": payload.platform,
                "audience_level": payload.audience_level,
                "niche_style": payload.niche_style,
                "title_target": payload.title_target,
                "use_live_trends": payload.use_live_trends,
                "suggested_duration": payload.suggested_duration,
                "scope": scope.to_dict(),
                "studio_version": self.STUDIO_VERSION,
            },
        )

        try:
            trend_payload: list[dict[str, Any]] = []
            trend_mode = "fallback_seed_expansion"
            if payload.use_live_trends and scope.scope != "specific":
                trend_payload, trend_mode = self._discover_trends(payload, language_code)

            bank = build_title_bank(
                topic=payload.topic,
                language_code=language_code,
                platform=payload.platform,
                audience_level=payload.audience_level,
                niche_style=payload.niche_style,
                title_target=max(1, payload.title_target),
                use_live_trends=payload.use_live_trends,
                suggested_duration=payload.suggested_duration,
                trend_opportunities=trend_payload,
                trend_mode=trend_mode,
            )
            result.title_bank = bank.to_dict()
            result.e2e_handoff = self._build_e2e_handoff(payload, bank)
            export_paths = self._export(result)
            result.export_paths = export_paths
            result.status = "completed"
        except Exception as exc:
            result.status = "failed"
            result.errors.append(str(exc))

        result.completed_at = _now_stamp()
        result.total_duration_ms = _ms(started)
        return result

    def build_e2e_payload(
        self,
        *,
        selected_title: str,
        source_run: TopicUniverseRunResult | dict[str, Any] | None = None,
        duration_seconds: int | None = None,
        platform: str | None = None,
        niche: str | None = None,
        mood: str | None = None,
    ) -> dict[str, Any]:
        run_dict = source_run.to_dict() if hasattr(source_run, "to_dict") else dict(source_run or {})
        input_payload = dict(run_dict.get("input") or {})
        return {
            "topic": selected_title.strip(),
            "duration_seconds": int(duration_seconds or input_payload.get("suggested_duration") or 30),
            "platform": platform or input_payload.get("platform") or "youtube_shorts",
            "niche": niche or input_payload.get("niche_style") or "general",
            "mood": mood or "instructional",
            "source_run_id": run_dict.get("run_id"),
            "handoff_type": "topic_universe_selected_title",
        }

    def _discover_trends(
        self,
        payload: TopicUniverseInput,
        language_code: str,
    ) -> tuple[list[dict[str, Any]], str]:
        profile = self.profile_loader.resolve(niche=payload.niche_style)
        localized = profile_with_output_language(profile, language_code)
        platform = self._resolve_platform(payload.platform)
        discovery = self.trend_engine.discover(
            profile=localized,
            niche=payload.niche_style,
            topic=payload.topic,
            platforms=[platform],
            max_results=25,
            use_provider_layer=True,
        )
        trends = []
        for opp in discovery.opportunities:
            meta = dict(getattr(opp, "metadata", {}) or {})
            trends.append(
                {
                    "trend": opp.topic,
                    "source": opp.source,
                    "score": float(opp.scores.overall_trend_score),
                    "provider_id": str(meta.get("provider_id") or opp.source),
                    "metadata": meta,
                }
            )
        trend_mode = classify_trend_sources(list(discovery.sources_used))
        if trend_mode == "mock_fallback":
            trend_mode = "fallback_seed_expansion"
        return trends, trend_mode

    def _export(self, result: TopicUniverseRunResult) -> dict[str, str]:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        base = self.export_dir / result.run_id
        json_path = base.with_suffix(".json")
        md_path = base.with_suffix(".md")
        csv_path = base.with_suffix(".csv")

        payload = result.to_dict()
        json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        md_path.write_text(self._render_markdown(result), encoding="utf-8")
        self._write_csv(csv_path, result)

        latest_json = self.export_dir / "latest.json"
        latest_md = self.export_dir / "latest.md"
        latest_csv = self.export_dir / "latest.csv"
        latest_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
        latest_csv.write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8", newline="")

        return {
            "json": str(json_path.resolve()),
            "markdown": str(md_path.resolve()),
            "csv": str(csv_path.resolve()),
            "latest_json": str(latest_json.resolve()),
            "latest_markdown": str(latest_md.resolve()),
            "latest_csv": str(latest_csv.resolve()),
        }

    @staticmethod
    def _write_csv(path: Path, result: TopicUniverseRunResult) -> None:
        titles = list((result.title_bank or {}).get("titles") or [])
        fieldnames = [
            "title_id",
            "title",
            "subtopic",
            "category",
            "intent",
            "difficulty",
            "estimated_viral_potential",
            "educational_value",
            "trend_score",
            "source_provider",
            "keywords",
            "suggested_duration",
            "suggested_clip_count",
            "content_strategy",
            "duplicate_status",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in titles:
                row = dict(item)
                row["keywords"] = ", ".join(row.get("keywords") or [])
                writer.writerow({key: row.get(key, "") for key in fieldnames})

    @staticmethod
    def _render_markdown(result: TopicUniverseRunResult) -> str:
        bank = result.title_bank or {}
        scope = bank.get("scope") or {}
        lines = [
            "# Topic Universe / SEO Title Bank",
            "",
            f"- Run ID: `{result.run_id}`",
            f"- Topic: **{bank.get('topic', result.input.get('topic', ''))}**",
            f"- Scope: `{scope.get('scope', '—')}`",
            f"- Mode: `{bank.get('mode', '—')}`",
            f"- Trend mode: `{bank.get('trend_mode', '—')}`",
            f"- Titles: **{bank.get('title_count', 0)}** / target {bank.get('title_target', 0)}",
            "",
            "## Notes",
        ]
        for note in bank.get("notes") or []:
            lines.append(f"- {note}")
        lines.extend(["", "## Titles", ""])
        for index, item in enumerate(bank.get("titles") or [], start=1):
            lines.append(f"{index}. **{item.get('title', '')}**")
            lines.append(
                f"   - subtopic: {item.get('subtopic')} · intent: {item.get('intent')} · "
                f"strategy: {item.get('content_strategy')} · source: {item.get('source_provider')}"
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _build_e2e_handoff(payload: TopicUniverseInput, bank: TitleBankResult) -> dict[str, Any]:
        first = bank.titles[0].title if bank.titles else payload.topic
        return {
            "ready": True,
            "recommended_topic_field": first,
            "mode": bank.mode,
            "instructions": (
                "Select any generated title and pass it as the topic into Content Brain E2E Micro Test."
            ),
        }

    @staticmethod
    def _coerce_input(spec: TopicUniverseInput | dict[str, Any]) -> TopicUniverseInput:
        if isinstance(spec, TopicUniverseInput):
            return spec
        return TopicUniverseInput(
            topic=str(spec.get("topic") or "").strip(),
            language_code=str(spec.get("language_code") or "").strip() or None,
            platform=str(spec.get("platform") or "youtube_shorts"),
            audience_level=str(spec.get("audience_level") or "general"),
            niche_style=str(spec.get("niche_style") or spec.get("niche") or "general"),
            title_target=int(spec.get("title_target") or spec.get("title_count") or DEFAULT_TITLE_TARGET),
            use_live_trends=bool(spec.get("use_live_trends", True)),
            suggested_duration=int(spec.get("suggested_duration") or spec.get("duration_seconds") or 30),
        )

    @staticmethod
    def _resolve_platform(value: str) -> Platform:
        cleaned = str(value or "youtube_shorts").strip().lower().replace("-", "_")
        aliases = {
            "youtube_shorts": Platform.YOUTUBE_SHORTS,
            "shorts": Platform.YOUTUBE_SHORTS,
            "tiktok": Platform.TIKTOK,
            "instagram_reels": Platform.INSTAGRAM_REELS,
            "reels": Platform.INSTAGRAM_REELS,
        }
        return aliases.get(cleaned, Platform.YOUTUBE_SHORTS)


def run_topic_universe_studio(**kwargs: Any) -> dict[str, Any]:
    studio = TopicUniverseStudio()
    result = studio.run(kwargs)
    return result.to_dict()


__all__ = [
    "DEFAULT_EXPORT_DIR",
    "TopicUniverseInput",
    "TopicUniverseRunResult",
    "TopicUniverseStudio",
    "run_topic_universe_studio",
]
