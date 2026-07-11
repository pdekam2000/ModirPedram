"""PHASE SUBTITLE-DELIVERY-LOCK — rebuild final MP4 with readable burned subtitles only."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_brain.branding.cta_engine import apply_cta_overlay
from content_brain.branding.subtitle_burn_engine import SUBTITLE_STYLE_TIKTOK, burn_subtitles
from content_brain.branding.subtitle_format_engine import measure_subtitle_text_bbox
from content_brain.platform.canonical_run import load_canonical_run
from content_brain.quality.delivery_reality_auditor import audit_final_mp4_delivery

from content_brain.platform.canonical_delivery import CANONICAL_BRANDED_VIDEO_NAME, promote_canonical_final_video
from content_brain.platform.final_delivery_registry import save_final_delivery_registry, load_final_delivery_registry
REPORT_PATH = ROOT / "project_brain" / "PHASE_SUBTITLE_DELIVERY_LOCK_REPORT.md"
OUTPUT_NAME = CANONICAL_BRANDED_VIDEO_NAME
BBOX_SAMPLES = (1.0, 3.0, 5.0, 8.0)


def _load_duration(publish_dir: Path) -> float:
    metadata_path = publish_dir / "metadata.json"
    if metadata_path.is_file():
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            return float(payload.get("duration_seconds") or 8.933878)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    return 8.933878


def _bbox_probe(video_path: Path) -> list[dict]:
    return [measure_subtitle_text_bbox(video_path, sample) for sample in BBOX_SAMPLES]


def _write_report(
    *,
    run_id: str,
    topic: str,
    before_video: Path,
    after_video: Path,
    before_bbox: list[dict],
    after_bbox: list[dict],
    burn_result: dict,
    audit_before: dict,
    audit_after: dict,
    approved: bool,
) -> None:
    lines = [
        "# PHASE SUBTITLE-DELIVERY-LOCK Report",
        "",
        f"- **Run ID:** `{run_id}`",
        f"- **Topic:** {topic}",
        f"- **Completed:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Root cause",
        "",
        "The delivered `FINAL_BRANDED_VIDEO.mp4` shipped without readable burned subtitles because branding marked the subtitle burn as failed and continued on the pre-subtitle video. CTA overlay was applied to the non-subtitled source, so the final MP4 failed the MP4-only subtitle bbox audit (`white_ratio` far below threshold).",
        "",
        "## Drawtext renderer fixes (`subtitle_format_engine_v6` / `subtitle_burn_engine_v8`)",
        "",
        "- Font size scaled to 5.2% of video height (min 52, preferred 64).",
        "- High-contrast outline: `borderw=6`, `bordercolor=black@1.0`.",
        "- Readable backing box: `box=1:boxcolor=black@0.55:boxborderw=12`.",
        "- Lower-third safe zone preserved via `compute_lower_third_margin_v()`.",
        "- Burn gate now verifies output frames with `measure_subtitle_text_bbox()` (height ≥ 18).",
        "",
        "## Before (delivered MP4 frame audit)",
        "",
        f"- Video: `{before_video}`",
        "",
        "| Sample (s) | Visible | White ratio | BBox W×H |",
        "|---|---:|---:|---:|",
    ]
    for row in before_bbox:
        bbox = row.get("bbox") or ["-", "-", "-", "-"]
        lines.append(
            f"| {row.get('sample_seconds')} | {row.get('visible')} | {row.get('white_ratio')} | "
            f"{row.get('bbox_width')}×{row.get('bbox_height')} |"
        )
    lines.extend(
        [
            "",
            f"- Delivery audit: **{audit_before.get('status')}** — failures: `{audit_before.get('failures')}`",
            "",
            "## After (`FINAL_BRANDED_VIDEO_subtitle_fixed.mp4`)",
            "",
            f"- Video: `{after_video}`",
            "",
            "| Sample (s) | Visible | White ratio | BBox W×H |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in after_bbox:
        lines.append(
            f"| {row.get('sample_seconds')} | {row.get('visible')} | {row.get('white_ratio')} | "
            f"{row.get('bbox_width')}×{row.get('bbox_height')} |"
        )
    lines.extend(
        [
            "",
            f"- Subtitle burn: `{burn_result.get('status')}` — visible enough: `{burn_result.get('burn_visible_enough')}`",
            f"- Delivery audit: **{audit_after.get('status')}** — checks: `{audit_after.get('checks')}`",
            f"- Failures: `{audit_after.get('failures')}`",
            f"- Approved: **{approved}**",
            "",
            "## Output",
            "",
            f"`{after_video}`",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    canonical = load_canonical_run(ROOT)
    publish_dir = Path(str(canonical.get("publish_dir") or "")).resolve()
    run_id = str(canonical.get("run_id") or "")
    topic = str(canonical.get("topic") or "")

    before_video = publish_dir / "FINAL_BRANDED_VIDEO.mp4"
    narrated_video = publish_dir / "FINAL_RUNWAY_PHASE_I_NARRATED.mp4"
    subtitle_path = publish_dir / "subtitles" / "subtitles.srt"
    staging = publish_dir / "subtitle_lock_staging"
    staging.mkdir(parents=True, exist_ok=True)

    if not narrated_video.is_file():
        raise SystemExit(f"missing narrated source: {narrated_video}")
    if not subtitle_path.is_file():
        raise SystemExit(f"missing subtitle srt: {subtitle_path}")

    before_bbox = _bbox_probe(before_video) if before_video.is_file() else []
    audit_before = audit_final_mp4_delivery(before_video) if before_video.is_file() else {"status": "FAIL", "failures": ["missing_before"]}

    subtitled_out = staging / "subtitled.mp4"
    burn = burn_subtitles(
        input_video_path=narrated_video,
        subtitle_path=subtitle_path,
        output_path=subtitled_out,
        subtitle_style=SUBTITLE_STYLE_TIKTOK,
    )
    burn_payload = burn.to_dict()
    burn_payload["burn_visible_enough"] = (burn.metadata or {}).get("burn_visible_enough")
    if burn.status != "COMPLETED":
        _write_report(
            run_id=run_id,
            topic=topic,
            before_video=before_video,
            after_video=output_video,
            before_bbox=before_bbox,
            after_bbox=[],
            burn_result=burn_payload,
            audit_before={"status": audit_before.status, "failures": audit_before.failures},
            audit_after={"status": "FAIL", "failures": ["subtitle_burn_failed"]},
            approved=False,
        )
        raise SystemExit(f"subtitle burn failed: {burn.error}")

    duration = _load_duration(publish_dir)
    cta_out = staging / "cta_overlay.mp4"
    cta = apply_cta_overlay(
        input_video_path=subtitled_out,
        output_path=cta_out,
        cta_text="Follow for more",
        cta_position="bottom_center",
        cta_frequency="end",
        duration_seconds=duration,
    )
    if cta.status != "COMPLETED":
        raise SystemExit(f"cta overlay failed: {cta.error}")

    output_video = promote_canonical_final_video(
        cta_out,
        publish_dir=publish_dir,
        archive_superseded=True,
        run_id=run_id,
    )
    after_bbox = _bbox_probe(output_video)
    audit_after = audit_final_mp4_delivery(output_video)

    approved = audit_after.status == "PASS"
    if approved:
        registry = load_final_delivery_registry(ROOT)
        registry.update(
            {
                "latest_run_id": run_id,
                "canonical_final_video_path": str(output_video.resolve()),
                "latest_publish_package": str(publish_dir.resolve()),
                "approved": True,
                "delivery_reality_passed": True,
                "topic": topic,
                "approved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        save_final_delivery_registry(ROOT, registry)

    _write_report(
        run_id=run_id,
        topic=topic,
        before_video=before_video,
        after_video=output_video,
        before_bbox=before_bbox,
        after_bbox=after_bbox,
        burn_result=burn_payload,
        audit_before={"status": audit_before.status, "failures": audit_before.failures, "checks": audit_before.checks},
        audit_after={"status": audit_after.status, "failures": audit_after.failures, "checks": audit_after.checks},
        approved=approved,
    )

    print(json.dumps({"output": str(output_video), "audit_status": audit_after.status, "approved": approved}, indent=2, ensure_ascii=False))
    return 0 if approved else 1


if __name__ == "__main__":
    raise SystemExit(main())
