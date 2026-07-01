"""Burn timed subtitles into final video — visible lower-third styling for vertical Shorts."""



from __future__ import annotations



from pathlib import Path

from typing import Any



from content_brain.branding.branding_ffmpeg import BrandingFfmpegResult, run_ffmpeg_filter

from content_brain.branding.subtitle_format_engine import (

    MIN_BURN_FONT_SIZE,

    POSITION_LOWER_THIRD,

    build_drawtext_subtitle_filter,

    compare_subtitle_burn_visibility,

    measure_subtitle_text_bbox,

    normalize_platform,

    prepare_ass_for_burn,

    probe_video_size,

    resolve_srt_content,

    validate_subtitle_visual_layout,

)



SUBTITLE_BURN_VERSION = "subtitle_burn_engine_v8"

SUBTITLED_VIDEO_NAME = "FINAL_RUNWAY_PHASE_I_SUBTITLED.mp4"

SHORTS_READABLE_MIN_HEIGHT = 18



SUBTITLE_STYLE_TIKTOK = "tiktok"

SUBTITLE_STYLE_INSTAGRAM = "instagram_reels"

SUBTITLE_STYLE_YOUTUBE = "youtube_shorts"



POSITION_BOTTOM_CENTER = "bottom_center"





def burn_subtitles(

    *,

    input_video_path: str | Path,

    subtitle_path: str | Path,

    output_path: str | Path | None = None,

    subtitle_style: str = SUBTITLE_STYLE_TIKTOK,

    subtitle_position: str = POSITION_LOWER_THIRD,

    ffmpeg_probe: Any | None = None,

    small_mode: bool = False,

) -> BrandingFfmpegResult:

    video = Path(input_video_path).resolve()

    subtitles = Path(subtitle_path)

    output = Path(output_path or video.parent / SUBTITLED_VIDEO_NAME).resolve()



    if not subtitles.is_file() or subtitles.stat().st_size <= 0:

        return BrandingFfmpegResult(

            status="SKIPPED",

            output_path=str(output),

            input_path=str(video),

            warnings=["subtitle_file_missing"],

        )



    style_key = subtitle_style if subtitle_style in {SUBTITLE_STYLE_TIKTOK, SUBTITLE_STYLE_INSTAGRAM, SUBTITLE_STYLE_YOUTUBE} else SUBTITLE_STYLE_TIKTOK

    platform_key = normalize_platform(style_key if style_key != SUBTITLE_STYLE_TIKTOK else "tiktok")



    burn_file, ass_meta = prepare_ass_for_burn(

        subtitles,

        video_path=video,

        platform=platform_key,

        small_mode=small_mode,

    )

    font_size = int(ass_meta.get("font_size") or MIN_BURN_FONT_SIZE)

    margin_v = int(ass_meta.get("margin_v") or 155)

    width, height = probe_video_size(video)



    layout_issues = validate_subtitle_visual_layout(

        platform=platform_key,

        font_size=font_size,

        margin_v=margin_v,

        line_count=2,

        alignment=2,

        video_height=int(ass_meta.get("video_height") or 1280),

    )



    raw_srt = resolve_srt_content(subtitles)

    if not raw_srt.strip():

        return BrandingFfmpegResult(

            status="FAILED",

            output_path=str(output),

            input_path=str(video),

            error="subtitle_srt_missing",

            warnings=["subtitle_srt_missing"],

        )



    vf, draw_meta = build_drawtext_subtitle_filter(

        srt_content=raw_srt,

        font_size=font_size,

        margin_v=margin_v,

    )

    if not vf:

        return BrandingFfmpegResult(

            status="FAILED",

            output_path=str(output),

            input_path=str(video),

            error="subtitle_drawtext_filter_empty",

            warnings=["subtitle_drawtext_filter_empty"],

        )



    result = run_ffmpeg_filter(

        input_path=video,

        output_path=output,

        vf_filter=vf,

        ffmpeg_probe=ffmpeg_probe,

        working_directory=None,

    )



    visibility = compare_subtitle_burn_visibility(

        before_video=video,

        after_video=output,

        sample_seconds=[1.0, 3.0, 5.0],

    )

    bbox_rows = [measure_subtitle_text_bbox(output, sample) for sample in (1.0, 3.0, 5.0) if output.is_file()]

    burn_visible = any(

        bool(row.get("visible")) and int(row.get("bbox_height") or 0) >= SHORTS_READABLE_MIN_HEIGHT

        for row in bbox_rows

    ) or bool(visibility.get("visible_enough"))

    if result.status == "COMPLETED" and not burn_visible:

        result.status = "FAILED"

        result.error = "subtitle_burn_not_visible"

    result.metadata.update(

        {

            "version": SUBTITLE_BURN_VERSION,

            "subtitle_style": style_key,

            "subtitle_position": subtitle_position or POSITION_LOWER_THIRD,

            "subtitle_path": str(burn_file.resolve()),

            "srt_path": str(subtitles.resolve()),

            "font_size": font_size,

            "margin_v": margin_v,

            "border_style": 1,

            "layout_quality_issues": layout_issues,

            "burn_psnr_avg": visibility.get("psnr_avg"),

            "burn_visible_enough": burn_visible,

            "burn_bbox_samples": bbox_rows,

            "vf_filter": vf[:500],

            **draw_meta,

        }

    )

    if layout_issues:

        result.warnings.extend(layout_issues)

    if not burn_visible:

        result.warnings.append("subtitle_burn_low_visibility")

    return result





__all__ = [

    "POSITION_BOTTOM_CENTER",

    "POSITION_LOWER_THIRD",

    "SUBTITLE_BURN_VERSION",

    "SUBTITLE_STYLE_INSTAGRAM",

    "SUBTITLE_STYLE_TIKTOK",

    "SUBTITLE_STYLE_YOUTUBE",

    "SUBTITLED_VIDEO_NAME",

    "burn_subtitles",

]

