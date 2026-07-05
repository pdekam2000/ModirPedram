"""CTA overlay suggestions and timed drawtext overlays — polished Shorts style."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from content_brain.branding.branding_ffmpeg import BrandingFfmpegResult, run_ffmpeg_filter

CTA_ENGINE_VERSION = "cta_engine_v3"
CTA_ACCENT_COLOUR = "0xFF7A1A"
CTA_DURATION_SECONDS = 2.8
CTA_FADE_SECONDS = 0.45

CTA_FREQUENCY_BEGINNING = "beginning"
CTA_FREQUENCY_MIDDLE = "middle"
CTA_FREQUENCY_END = "end"

DEFAULT_CTA_SUGGESTIONS = (
    "Follow for more",
    "Subscribe for more",
    "Like & Follow",
    "Follow @channelname",
)

CTA_PRESETS: dict[str, str] = {
    "follow_for_more": "Follow for more",
    "subscribe": "Subscribe",
    "like_and_follow": "Like & Follow",
    "custom": "",
}

RULE_BASED_CTAS = {
    "tiktok": ("Follow for more", "Like and follow"),
    "instagram_reels": ("Follow @channelname", "Follow for more"),
    "youtube_shorts": ("Subscribe for more", "What should we cover next?"),
}


def _escape_drawtext(text: str) -> str:
    cleaned = str(text or "").replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return cleaned[:120]


def resolve_cta_text(
    *,
    profile: dict[str, Any] | None = None,
    channel_name: str = "",
    platform: str = "tiktok",
    topic: str = "",
    use_openai: bool = True,
) -> tuple[str, list[str], str]:
    profile = dict(profile or {})
    preset = str(profile.get("cta_preset") or "follow_for_more").strip().lower()
    custom = str(profile.get("cta_custom_slogan") or profile.get("cta_text") or "").strip()
    if preset == "custom" and custom:
        suggestions, source = suggest_cta_texts(
            channel_name=channel_name or str(profile.get("channel_name") or ""),
            platform=platform or str(profile.get("default_platform") or "tiktok"),
            topic=topic,
            use_openai=use_openai,
        )
        return custom, suggestions, "custom_slogan"
    if preset in CTA_PRESETS and CTA_PRESETS[preset]:
        text = CTA_PRESETS[preset]
        if preset == "follow_for_more" and channel_name:
            handle = re.sub(r"[^a-zA-Z0-9_]", "", channel_name.replace(" ", ""))
            if handle:
                text = f"Follow @{handle} for more"
        suggestions, source = suggest_cta_texts(
            channel_name=channel_name or str(profile.get("channel_name") or ""),
            platform=platform,
            topic=topic,
            use_openai=use_openai,
        )
        return text, [text, *suggestions], source
    suggestions, source = suggest_cta_texts(
        channel_name=channel_name or str(profile.get("channel_name") or ""),
        platform=platform,
        topic=topic,
        use_openai=use_openai,
    )
    return (suggestions[0] if suggestions else "Follow for more"), suggestions, source


def suggest_cta_texts(
    *,
    channel_name: str = "",
    platform: str = "tiktok",
    topic: str = "",
    use_openai: bool = True,
) -> tuple[list[str], str]:
    platform_key = str(platform or "tiktok").strip().lower()
    fallback = list(RULE_BASED_CTAS.get(platform_key, DEFAULT_CTA_SUGGESTIONS))
    if channel_name:
        handle = re.sub(r"[^a-zA-Z0-9_]", "", channel_name.replace(" ", ""))
        if handle:
            fallback.append(f"Follow @{handle}")

    if not use_openai:
        return fallback[:4], "rule_based"

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return fallback[:4], "rule_based_no_api_key"

    try:
        from openai import OpenAI
    except ImportError:
        return fallback[:4], "rule_based_no_openai_package"

    prompt = {
        "channel_name": channel_name,
        "platform": platform_key,
        "topic": topic,
        "examples": list(DEFAULT_CTA_SUGGESTIONS),
    }
    try:
        client = OpenAI(api_key=api_key, timeout=30.0)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Return JSON: {\"cta_suggestions\": [\"...\"]} with 3-4 short CTA lines for short-form video.",
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            temperature=0.4,
            max_tokens=200,
        )
        raw = (response.choices[0].message.content or "").strip()
        payload = json.loads(raw)
        suggestions = [str(item).strip() for item in (payload.get("cta_suggestions") or []) if str(item).strip()]
        if suggestions:
            return suggestions[:4], "openai"
    except Exception:
        pass
    return fallback[:4], "rule_based"


def _cta_window(
    duration_seconds: float,
    frequency: str,
    *,
    cta_start_seconds: float | None = None,
    cta_end_seconds: float | None = None,
) -> tuple[float, float]:
    duration = max(1.0, float(duration_seconds or 10.0))
    if cta_start_seconds is not None and cta_end_seconds is not None:
        start = max(0.0, float(cta_start_seconds))
        end = min(duration, float(cta_end_seconds))
        if end <= start:
            end = min(duration, start + CTA_DURATION_SECONDS)
        return start, end
    span = min(CTA_DURATION_SECONDS, max(2.0, duration * 0.12))
    if frequency == CTA_FREQUENCY_BEGINNING:
        return 0.0, min(span, duration * 0.25)
    if frequency == CTA_FREQUENCY_MIDDLE:
        start = max(0.0, duration * 0.42)
        return start, min(duration, start + span)
    start = max(0.0, duration - span)
    return start, duration


def _cta_position_exprs(position: str) -> tuple[str, str]:
    normalized = str(position or "bottom_center").strip().lower()
    if normalized == "top_left":
        return "48", "96"
    if normalized == "top_right":
        return "w-text_w-48", "96"
    return "(w-text_w)/2", "h-th-88"


def apply_cta_overlay(
    *,
    input_video_path: str | Path,
    output_path: str | Path,
    cta_text: str,
    cta_position: str = "bottom_center",
    cta_frequency: str = CTA_FREQUENCY_END,
    cta_start_seconds: float | None = None,
    cta_end_seconds: float | None = None,
    duration_seconds: float | None = None,
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    video = Path(input_video_path)
    output = Path(output_path)
    text = _escape_drawtext(cta_text or "Follow for more")
    if not text:
        return BrandingFfmpegResult(
            status="SKIPPED",
            output_path=str(output),
            input_path=str(video),
            warnings=["cta_text_empty"],
        )

    duration = float(duration_seconds or 30.0)
    start, end = _cta_window(
        duration,
        cta_frequency,
        cta_start_seconds=cta_start_seconds,
        cta_end_seconds=cta_end_seconds,
    )
    fade = min(CTA_FADE_SECONDS, max(0.2, (end - start) * 0.25))
    x_expr, y_expr = _cta_position_exprs(cta_position)
    alpha_in = f"if(lt(t,{start + fade:.2f}),(t-{start:.2f})/{fade:.2f},1)"
    alpha_out = f"if(gt(t,{end - fade:.2f}),({end:.2f}-t)/{fade:.2f},1)"
    alpha_expr = f"if(lt(t,{start:.2f}),0,if(gt(t,{end:.2f}),0,min({alpha_in},{alpha_out})))"

    vf = (
        f"drawtext=text='{text}':fontcolor={CTA_ACCENT_COLOUR}:fontsize=22:borderw=2:bordercolor=black@0.9:"
        f"box=1:boxcolor=black@0.45:boxborderw=14:"
        f"x={x_expr}:y={y_expr}:alpha='{alpha_expr}'"
    )
    result = run_ffmpeg_filter(
        input_path=video,
        output_path=output,
        vf_filter=vf,
        ffmpeg_probe=ffmpeg_probe,
    )
    result.metadata.update(
        {
            "version": CTA_ENGINE_VERSION,
            "cta_text": cta_text,
            "cta_position": cta_position,
            "cta_frequency": cta_frequency,
            "cta_start_seconds": cta_start_seconds,
            "cta_end_seconds": cta_end_seconds,
            "cta_window": {"start": start, "end": end},
            "cta_fade_seconds": fade,
            "cta_accent_colour": CTA_ACCENT_COLOUR,
        }
    )
    return result


def _graphic_overlay_coords(position: str) -> str:
    normalized = str(position or "bottom_center").strip().lower()
    if normalized == "bottom_left":
        return "48:H-h-48"
    if normalized == "bottom_right":
        return "W-w-48:H-h-48"
    return "(W-w)/2:H-h-48"


def apply_cta_graphic_overlay(
    *,
    input_video_path: str | Path,
    output_path: str | Path,
    graphic_path: str | Path,
    cta_position: str = "bottom_center",
    duration_seconds: float = 30.0,
    graphic_duration_seconds: float = 5.0,
    ffmpeg_probe: Any | None = None,
) -> BrandingFfmpegResult:
    from content_brain.branding.branding_ffmpeg import run_ffmpeg_complex

    video = Path(input_video_path)
    output = Path(output_path)
    graphic = Path(graphic_path)
    if not graphic.is_file() or graphic.stat().st_size <= 0:
        return BrandingFfmpegResult(
            status="SKIPPED",
            output_path=str(output),
            input_path=str(video),
            warnings=["cta_graphic_missing"],
        )

    duration = max(1.0, float(duration_seconds or 30.0))
    show_for = max(1.0, min(float(graphic_duration_seconds or 5.0), duration))
    start = max(0.0, duration - show_for)
    coords = _graphic_overlay_coords(cta_position)
    enable_expr = f"between(t,{start:.2f},{duration:.2f})"
    filter_complex = (
        f"[1:v]scale=iw*0.42:-1[ctaimg];"
        f"[0:v][ctaimg]overlay={coords}:enable='{enable_expr}'[vout]"
    )
    result = run_ffmpeg_complex(
        input_paths=[video, graphic],
        output_path=output,
        filter_complex=filter_complex,
        map_args=["-map", "[vout]", "-map", "0:a?"],
        ffmpeg_probe=ffmpeg_probe,
    )
    result.metadata.update(
        {
            "version": CTA_ENGINE_VERSION,
            "cta_style": "graphic_overlay",
            "cta_graphic_path": str(graphic.resolve()),
            "cta_graphic_window": {"start": start, "end": duration, "duration": show_for},
        }
    )
    return result


__all__ = [
    "CTA_ACCENT_COLOUR",
    "CTA_ENGINE_VERSION",
    "CTA_FREQUENCY_BEGINNING",
    "CTA_FREQUENCY_END",
    "CTA_FREQUENCY_MIDDLE",
    "CTA_PRESETS",
    "apply_cta_graphic_overlay",
    "apply_cta_overlay",
    "resolve_cta_text",
    "suggest_cta_texts",
]
