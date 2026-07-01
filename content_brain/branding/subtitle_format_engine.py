"""Short-form subtitle formatting — lower-third safe zones, line limits, keyword highlights."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

SUBTITLE_FORMAT_VERSION = "subtitle_format_engine_v6"
MAX_WORDS_PER_LINE = 4
MAX_LINES_PER_CUE = 2
# Line-break planning only — not burn size.
PLANNING_FONT_SIZE = 14
MIN_BURN_FONT_SIZE = 52
PREFERRED_BURN_FONT_SIZE = 64
MAX_BURN_FONT_SIZE = 76
MAX_SCREEN_COVERAGE_PERCENT = 22.0
MAX_SUBTITLE_PSNR_DB = 42.0
MIN_SUBTITLE_WHITE_RATIO = 0.004
MIN_SUBTITLE_BBOX_WIDTH = 100
MIN_SUBTITLE_BBOX_HEIGHT = 14
SHORTS_SUBTITLE_BORDER_WIDTH = 6
SHORTS_SUBTITLE_BOX_OPACITY = 0.55

POSITION_LOWER_THIRD = "lower_third"
POSITION_BOTTOM_CENTER = "bottom_center"

PLATFORM_SAFE_MARGINS: dict[str, dict[str, int]] = {
    "tiktok": {"margin_v": 160, "margin_l": 56, "margin_r": 56, "alignment": 2},
    "instagram_reels": {"margin_v": 150, "margin_l": 52, "margin_r": 52, "alignment": 2},
    "youtube_shorts": {"margin_v": 155, "margin_l": 48, "margin_r": 48, "alignment": 2},
    "default": {"margin_v": 155, "margin_l": 48, "margin_r": 48, "alignment": 2},
}

HIGHLIGHT_COLOURS_BGR = (
    "&H00A1FF7A",  # orange accent
    "&H0000FFFF",  # yellow
    "&H00FFFF00",  # cyan
)
DEFAULT_PRIMARY_COLOUR = "&H00FFFFFF"
DEFAULT_OUTLINE_COLOUR = "&H00000000"

_TECHNICAL_JUNK = re.compile(
    r"\b(highlighting|weaving in|Advanced Character Animation Techniques|Environmental Storytelling|"
    r"Behavioral Anthropomorphism|Visual Narrative Pacing|Short-Form Documentaries)\b[^.]*",
    re.IGNORECASE,
)


def normalize_platform(platform: str) -> str:
    key = str(platform or "tiktok").strip().lower()
    if "instagram" in key or "reels" in key:
        return "instagram_reels"
    if "youtube" in key or "shorts" in key:
        return "youtube_shorts"
    if "tiktok" in key:
        return "tiktok"
    return "default"


def _platform_margins(platform: str) -> dict[str, int]:
    return dict(PLATFORM_SAFE_MARGINS.get(normalize_platform(platform), PLATFORM_SAFE_MARGINS["default"]))


def probe_video_size(video_path: str | Path) -> tuple[int, int]:
    path = Path(video_path)
    if not path.is_file():
        return 720, 1280
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if proc.returncode != 0:
            return 720, 1280
        parts = [part.strip() for part in (proc.stdout or "").split(",") if part.strip()]
        if len(parts) >= 2:
            return max(1, int(parts[0])), max(1, int(parts[1]))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return 720, 1280


def compute_burn_font_size(video_height: int, *, small_mode: bool = False) -> int:
    height = max(480, int(video_height or 1280))
    scaled = round(height * 0.052)
    if small_mode:
        return max(MIN_BURN_FONT_SIZE, min(scaled, MAX_BURN_FONT_SIZE))
    target = max(PREFERRED_BURN_FONT_SIZE, scaled)
    return max(MIN_BURN_FONT_SIZE, min(target, MAX_BURN_FONT_SIZE))


def compute_lower_third_margin_v(video_height: int, platform: str = "tiktok") -> int:
    margins = _platform_margins(platform)
    base = int(margins["margin_v"])
    # Keep subtitles in lower 18–24% band on vertical Shorts.
    dynamic = int(round(video_height * 0.14))
    return max(130, min(180, max(base, dynamic)))


def break_cue_into_short_lines(text: str, *, platform: str = "tiktok", max_words: int | None = None) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return []
    limit = max(2, min(int(max_words or MAX_WORDS_PER_LINE), MAX_WORDS_PER_LINE))
    words = cleaned.split()
    lines: list[str] = []
    bucket: list[str] = []
    for word in words:
        bucket.append(word)
        if len(bucket) >= limit:
            lines.append(" ".join(bucket))
            bucket = []
            if len(lines) >= MAX_LINES_PER_CUE:
                break
    if bucket and len(lines) < MAX_LINES_PER_CUE:
        lines.append(" ".join(bucket))
    return lines[:MAX_LINES_PER_CUE]


def _extract_keywords(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z']{4,}", text)
    stop = {"this", "that", "with", "from", "into", "about", "your", "their", "watch", "follow", "scene", "explores"}
    return {word.lower() for word in words if word.lower() not in stop}


def _highlight_ass_line(line: str, keywords: set[str]) -> str:
    parts: list[str] = []
    for index, word in enumerate(line.split()):
        core = re.sub(r"[^A-Za-z']", "", word)
        if core.lower() in keywords and len(core) >= 4:
            colour = HIGHLIGHT_COLOURS_BGR[index % len(HIGHLIGHT_COLOURS_BGR)]
            parts.append(r"{\c" + colour + r"&}" + word + r"{\c" + DEFAULT_PRIMARY_COLOUR + r"&}")
        else:
            parts.append(word)
    return " ".join(parts)


def ass_contains_highlight_colours(ass_content: str) -> bool:
    return any(colour in ass_content for colour in HIGHLIGHT_COLOURS_BGR)


def export_subtitle_style_preview(ass_content: str, output_path: str | Path, *, font_size: int | None = None) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    size = int(font_size or PREFERRED_BURN_FONT_SIZE)
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        path.write_bytes(b"")
        return str(path)
    image = Image.new("RGB", (720, 1280), color=(12, 12, 18))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    y = int(1280 * 0.78)
    x = 48
    for text, colour in (
        ("Introduce the cute ", (255, 255, 255)),
        ("orange cat", (255, 122, 26)),
        (" explorer", (255, 255, 0)),
    ):
        draw.text((x, y), text, fill=colour, font=font)
        x += int(draw.textlength(text, font=font))
    draw.rectangle((36, y - 12, 684, y + size + 24), outline=(255, 122, 26), width=2)
    image.save(path)
    return str(path.resolve())


def validate_shorts_subtitle_cue(text: str, *, platform: str = "tiktok") -> list[str]:
    warnings: list[str] = []
    lines = break_cue_into_short_lines(text, platform=platform)
    if not lines:
        warnings.append("empty_cue")
        return warnings
    if len(lines) > MAX_LINES_PER_CUE:
        warnings.append("too_many_lines")
    for line in lines:
        if len(line.split()) > MAX_WORDS_PER_LINE:
            warnings.append("line_too_long")
    if len(text) > 80:
        warnings.append("cue_too_long")
    return warnings


def validate_subtitle_visual_layout(
    *,
    platform: str = "tiktok",
    font_size: int = PREFERRED_BURN_FONT_SIZE,
    margin_v: int | None = None,
    line_count: int = 1,
    alignment: int = 2,
    video_height: int = 1280,
) -> list[str]:
    issues: list[str] = []
    margins = _platform_margins(platform)
    resolved_margin_v = int(margin_v if margin_v is not None else compute_lower_third_margin_v(video_height, platform))
    if font_size < MIN_BURN_FONT_SIZE:
        issues.append("burn_font_size_too_small")
    if line_count > MAX_LINES_PER_CUE:
        issues.append("more_than_two_lines_visible")
    if resolved_margin_v < 130 or resolved_margin_v > 180:
        issues.append("subtitle_margin_outside_lower_third_band")
    if alignment not in {1, 2, 3}:
        issues.append("subtitle_not_bottom_aligned")
    if resolved_margin_v < 120:
        issues.append("subtitle_in_center_region")
    return issues


def _parse_srt_blocks(raw: str) -> list[tuple[str, str, str]]:
    blocks = re.split(r"\n\s*\n", raw.strip())
    parsed: list[tuple[str, str, str]] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        index = lines[0]
        timing = lines[1]
        text = "\n".join(lines[2:])
        parsed.append((index, timing, text))
    return parsed


def _srt_timestamp_to_seconds(timestamp: str) -> float:
    cleaned = str(timestamp or "").strip().replace(",", ".")
    parts = cleaned.split(":")
    if len(parts) != 3:
        return 0.0
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    except ValueError:
        return 0.0
    return hours * 3600 + minutes * 60 + seconds


def parse_srt_timing(timing: str) -> tuple[float, float]:
    match = re.match(r"(\S+)\s*-->\s*(\S+)", str(timing or "").strip())
    if not match:
        return 0.0, 0.0
    return _srt_timestamp_to_seconds(match.group(1)), _srt_timestamp_to_seconds(match.group(2))


def _escape_drawtext(text: str) -> str:
    cleaned = (
        str(text or "")
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\u2019")
        .replace("%", "\\%")
    )
    return cleaned[:240]


def _escape_ffmpeg_path(path: Path) -> str:
    text = path.resolve().as_posix()
    if len(text) >= 2 and text[1] == ":":
        return text[0] + "\\\\:" + text[2:]
    return text.replace(":", "\\:")


def resolve_srt_content(subtitle_path: str | Path) -> str:
    source = Path(subtitle_path)
    if source.suffix.lower() == ".srt" and source.is_file():
        return source.read_text(encoding="utf-8")
    for candidate in (source.with_suffix(".srt"), source.parent / "subtitles.srt"):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return ""


def _strip_speaker_prefix(text: str) -> str:
    cleaned = re.sub(r"^[^\w\s]+\s*", "", str(text or "").strip())
    return re.sub(r"^[A-Za-z][A-Za-z0-9 _-]{0,20}:\s*", "", cleaned).strip()


def build_drawtext_subtitle_filter(
    *,
    srt_content: str,
    font_size: int = PREFERRED_BURN_FONT_SIZE,
    margin_v: int = 155,
    font_file: str | Path = "C:/Windows/Fonts/arial.ttf",
) -> tuple[str, dict[str, Any]]:
    """Build ffmpeg drawtext chain — reliable subtitle burn on full MP4 re-encode."""
    font_path = Path(font_file)
    if not font_path.is_file():
        font_path = Path("C:/Windows/Fonts/arial.ttf")
    font_esc = _escape_ffmpeg_path(font_path)
    filters: list[str] = []
    cue_count = 0
    for _index, timing, text in _parse_srt_blocks(srt_content):
        start, end = parse_srt_timing(timing)
        if end <= start:
            continue
        plain = _strip_ass_override_tags(_strip_speaker_prefix(text)).strip()
        if not plain:
            continue
        escaped = _escape_drawtext(plain.replace("\n", r"\n"))
        border_w = SHORTS_SUBTITLE_BORDER_WIDTH
        box_opacity = SHORTS_SUBTITLE_BOX_OPACITY
        filters.append(
            "drawtext="
            f"text='{escaped}':fontfile={font_esc}:fontsize={int(font_size)}:"
            "fontcolor=white@1.0:"
            f"borderw={border_w}:bordercolor=black@1.0:"
            f"box=1:boxcolor=black@{box_opacity}:boxborderw=12:"
            f"x=(w-text_w)/2:y=h-th-{int(margin_v)}:"
            f"enable='between(t,{start:.3f},{end:.3f})'"
        )
        cue_count += 1
    meta = {
        "burn_method": "drawtext",
        "cue_count": cue_count,
        "font_size": int(font_size),
        "margin_v": int(margin_v),
        "border_width": SHORTS_SUBTITLE_BORDER_WIDTH,
        "box_opacity": SHORTS_SUBTITLE_BOX_OPACITY,
        "font_file": str(font_path.resolve()) if font_path.is_file() else "",
    }
    return ",".join(filters), meta


def format_srt_content(raw_srt: str, *, platform: str = "tiktok") -> tuple[str, dict[str, Any]]:
    platform_key = normalize_platform(platform)
    margins = _platform_margins(platform_key)
    out_blocks: list[str] = []
    cue_index = 1
    max_lines_seen = 0

    for _index, timing, text in _parse_srt_blocks(raw_srt):
        lines = break_cue_into_short_lines(text, platform=platform_key)
        if not lines:
            continue
        max_lines_seen = max(max_lines_seen, len(lines))
        formatted_text = "\n".join(lines)
        out_blocks.extend([str(cue_index), timing, formatted_text, ""])
        cue_index += 1

    meta = {
        "version": SUBTITLE_FORMAT_VERSION,
        "platform": platform_key,
        "max_words_per_line": MAX_WORDS_PER_LINE,
        "max_lines_per_cue": MAX_LINES_PER_CUE,
        "safe_margin_v": margins["margin_v"],
        "cue_count": max(0, cue_index - 1),
        "max_lines_seen": max_lines_seen,
    }
    return "\n".join(out_blocks).strip() + "\n", meta


def _strip_ass_override_tags(text: str) -> str:
    return re.sub(r"\{\\[^}]+\}", "", str(text or ""))


def measure_subtitle_text_bbox(
    video_path: str | Path,
    sample_seconds: float,
    *,
    crop_filter: str = "crop=iw:ih*24/100:0:ih-ih*24/100",
) -> dict[str, Any]:
    """Detect human-visible subtitle text in lower-third via bright pixel clustering."""
    video = Path(video_path)
    result: dict[str, Any] = {
        "sample_seconds": sample_seconds,
        "visible": False,
        "white_ratio": 0.0,
        "bbox": None,
        "bbox_width": 0,
        "bbox_height": 0,
    }
    if not video.is_file():
        result["error"] = "missing_video"
        return result
    png = video.with_suffix(f".subtitle_bbox_{sample_seconds:.2f}.png")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(sample_seconds),
                "-i",
                str(video),
                "-vf",
                crop_filter,
                "-frames:v",
                "1",
                str(png),
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
        if not png.is_file():
            result["error"] = "frame_extract_failed"
            return result
        from PIL import Image

        try:
            import numpy as np

            arr = np.array(Image.open(png))
            white = (arr[:, :, 0] > 205) & (arr[:, :, 1] > 205) & (arr[:, :, 2] > 205)
            white_ratio = float(white.mean())
            result["white_ratio"] = round(white_ratio, 6)
            ys, xs = np.where(white)
            if len(xs) == 0:
                return result
            bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        except ImportError:
            img = Image.open(png).convert("RGB")
            pixels = list(img.getdata())
            width, height = img.size
            white_count = 0
            xs: list[int] = []
            ys: list[int] = []
            for index, (r, g, b) in enumerate(pixels):
                if r > 205 and g > 205 and b > 205:
                    white_count += 1
                    xs.append(index % width)
                    ys.append(index // width)
            white_ratio = white_count / max(1, len(pixels))
            result["white_ratio"] = round(white_ratio, 6)
            if not xs:
                return result
            bbox = [min(xs), min(ys), max(xs), max(ys)]
        width = bbox[2] - bbox[0] + 1
        height = bbox[3] - bbox[1] + 1
        result["bbox"] = bbox
        result["bbox_width"] = width
        result["bbox_height"] = height
        result["visible"] = bool(
            result["white_ratio"] >= MIN_SUBTITLE_WHITE_RATIO
            and width >= MIN_SUBTITLE_BBOX_WIDTH
            and height >= MIN_SUBTITLE_BBOX_HEIGHT
        )
        return result
    except Exception as exc:  # noqa: BLE001 — forensic probe path
        result["error"] = str(exc)[:200]
        return result
    finally:
        png.unlink(missing_ok=True)


def format_ass_content_for_burn(
    srt_content: str,
    *,
    platform: str = "tiktok",
    video_width: int = 720,
    video_height: int = 1280,
    small_mode: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Plain white ASS for reliable libass burn — no inline colour override tags."""
    formatted_srt, meta = format_srt_content(srt_content, platform=platform)
    platform_key = normalize_platform(platform)
    margins = _platform_margins(platform_key)
    font_size = compute_burn_font_size(video_height, small_mode=small_mode)
    margin_v = compute_lower_third_margin_v(video_height, platform_key)
    style = (
        f"Style: ShortsLowerThird,Arial,{font_size},"
        f"{DEFAULT_PRIMARY_COLOUR},{DEFAULT_OUTLINE_COLOUR},&H00000000,"
        f"{DEFAULT_OUTLINE_COLOUR},&H00000000,-1,0,0,0,100,100,0,0,1,4,2,{margins['alignment']},"
        f"{margins['margin_l']},{margin_v},{margins['margin_r']},1"
    )
    header = [
        "[Script Info]",
        "Title: ModirAgentOS Shorts Subtitles",
        "ScriptType: v4.00+",
        f"PlayResX: {max(1, int(video_width))}",
        f"PlayResY: {max(1, int(video_height))}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginV, MarginR, Encoding",
        style,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def _ass_time(value: str) -> str:
        hh, mm, rest = value.split(":")
        ss, ms = rest.replace(",", ".").split(".")
        return f"{int(hh)}:{mm}:{ss}.{ms[:2]}"

    events: list[str] = []
    for _index, timing, text in _parse_srt_blocks(formatted_srt):
        start_raw, end_raw = timing.split("-->")
        start = _ass_time(start_raw.strip())
        end = _ass_time(end_raw.strip())
        lines = break_cue_into_short_lines(text.replace("\n", " "), platform=platform_key)
        if not lines:
            continue
        plain = "\\N".join(lines)
        events.append(f"Dialogue: 0,{start},{end},ShortsLowerThird,,0,0,0,,{plain}")

    meta.update(
        {
            "ass_path_ready": True,
            "font_size": font_size,
            "margin_v": margin_v,
            "video_width": video_width,
            "video_height": video_height,
            "plain_burn_ass": True,
        }
    )
    return "\n".join(header + events) + "\n", meta


def format_ass_content(
    raw_srt: str,
    *,
    platform: str = "tiktok",
    video_width: int = 720,
    video_height: int = 1280,
    small_mode: bool = False,
) -> tuple[str, dict[str, Any]]:
    formatted_srt, meta = format_srt_content(raw_srt, platform=platform)
    platform_key = normalize_platform(platform)
    margins = _platform_margins(platform_key)
    keywords = _extract_keywords(formatted_srt)
    font_size = compute_burn_font_size(video_height, small_mode=small_mode)
    margin_v = compute_lower_third_margin_v(video_height, platform_key)

    style = (
        f"Style: ShortsLowerThird,Arial,{font_size},"
        f"{DEFAULT_PRIMARY_COLOUR},{DEFAULT_OUTLINE_COLOUR},&H00000000,"
        f"{DEFAULT_OUTLINE_COLOUR},&H00000000,-1,0,0,0,100,100,0,0,1,4,2,{margins['alignment']},"
        f"{margins['margin_l']},{margin_v},{margins['margin_r']},1"
    )
    header = [
        "[Script Info]",
        "Title: ModirAgentOS Shorts Subtitles",
        "ScriptType: v4.00+",
        f"PlayResX: {max(1, int(video_width))}",
        f"PlayResY: {max(1, int(video_height))}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginV, MarginR, Encoding",
        style,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def _ass_time(value: str) -> str:
        hh, mm, rest = value.split(":")
        ss, ms = rest.replace(",", ".").split(".")
        return f"{int(hh)}:{mm}:{ss}.{ms[:2]}"

    events: list[str] = []
    for _index, timing, text in _parse_srt_blocks(formatted_srt):
        start_raw, end_raw = timing.split("-->")
        start = _ass_time(start_raw.strip())
        end = _ass_time(end_raw.strip())
        lines = break_cue_into_short_lines(text.replace("\n", " "), platform=platform_key)
        if not lines:
            continue
        highlighted = "\\N".join(_highlight_ass_line(line, keywords) for line in lines)
        events.append(f"Dialogue: 0,{start},{end},ShortsLowerThird,,0,0,0,,{highlighted}")

    meta.update(
        {
            "ass_path_ready": True,
            "font_size": font_size,
            "margin_v": margin_v,
            "video_width": video_width,
            "video_height": video_height,
            "highlight_colours": list(HIGHLIGHT_COLOURS_BGR),
            "styled_ass": True,
        }
    )
    return "\n".join(header + events) + "\n", meta


def prepare_ass_for_burn(
    ass_path: str | Path,
    *,
    video_path: str | Path,
    platform: str = "tiktok",
    small_mode: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """Rewrite ASS style for target video resolution without clobbering inline highlight tags."""
    source = Path(ass_path)
    width, height = probe_video_size(video_path)
    raw_srt = ""
    if source.suffix.lower() == ".srt":
        raw_srt = source.read_text(encoding="utf-8")
    else:
        for candidate in (source.with_suffix(".srt"), source.parent / "subtitles.srt"):
            if candidate.is_file():
                raw_srt = candidate.read_text(encoding="utf-8")
                break
        if not raw_srt and source.is_file():
            raw_srt = source.read_text(encoding="utf-8")
    if not raw_srt.strip():
        return source, {"font_size": compute_burn_font_size(height, small_mode=small_mode)}

    ass_content, meta = format_ass_content_for_burn(
        raw_srt,
        platform=platform,
        video_width=width,
        video_height=height,
        small_mode=small_mode,
    )
    target = source if source.suffix.lower() == ".ass" else source.with_suffix(".ass")
    target.write_text(ass_content, encoding="utf-8")
    return target, meta


def compare_subtitle_burn_visibility(
    *,
    before_video: str | Path,
    after_video: str | Path,
    sample_seconds: float | list[float] = 0.5,
) -> dict[str, Any]:
    """Compare lower-third crop at subtitle timestamps — requires visible pixel change."""
    before = Path(before_video)
    after = Path(after_video)
    samples = sample_seconds if isinstance(sample_seconds, list) else [float(sample_seconds)]
    result: dict[str, Any] = {
        "sample_seconds": samples,
        "psnr_avg": None,
        "changed_pixel_ratio": None,
        "visible_enough": False,
        "samples": [],
    }
    if not before.is_file() or not after.is_file():
        result["error"] = "missing_video"
        return result

    crop = "crop=iw:ih*24/100:0:ih-ih*24/100"
    psnr_values: list[float] = []
    ratio_values: list[float] = []
    sample_rows: list[dict[str, Any]] = []

    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        Image = None  # type: ignore[assignment,misc]
        np = None  # type: ignore[assignment,misc]

    for seek in samples:
        before_png = before.with_suffix(f".visibility_before_{seek:.2f}.png")
        after_png = after.with_suffix(f".visibility_after_{seek:.2f}.png")
        row = {"sample_seconds": seek, "psnr_avg": None, "changed_pixel_ratio": None, "visible_enough": False}
        try:
            for src, dst in ((before, before_png), (after, after_png)):
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-ss",
                        str(seek),
                        "-i",
                        str(src),
                        "-vf",
                        crop,
                        "-frames:v",
                        "1",
                        str(dst),
                    ],
                    capture_output=True,
                    timeout=60,
                    check=False,
                )
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-i",
                    str(before_png),
                    "-i",
                    str(after_png),
                    "-filter_complex",
                    "[0:v][1:v]psnr=stats_file=-",
                    "-frames:v",
                    "1",
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            match = re.search(r"average:(\d+(?:\.\d+)?)", proc.stderr or "")
            if match:
                row["psnr_avg"] = float(match.group(1))
                psnr_values.append(row["psnr_avg"])

            if Image is not None and before_png.is_file() and after_png.is_file():
                before_img = Image.open(before_png).convert("RGB")
                after_img = Image.open(after_png).convert("RGB")
                if before_img.size == after_img.size:
                    if np is not None:
                        before_arr = np.array(before_img)
                        after_arr = np.array(after_img)
                        diff = np.abs(after_arr.astype(int) - before_arr.astype(int))
                        row["changed_pixel_ratio"] = round(float((diff.max(axis=2) > 24).mean()), 5)
                    else:
                        changed = 0
                        total = 0
                        for left, right in zip(before_img.getdata(), after_img.getdata()):
                            total += 1
                            if max(abs(left[0] - right[0]), abs(left[1] - right[1]), abs(left[2] - right[2])) > 24:
                                changed += 1
                        row["changed_pixel_ratio"] = round(changed / max(1, total), 5)
                    ratio_values.append(row["changed_pixel_ratio"])
        except (OSError, subprocess.TimeoutExpired) as exc:
            row["error"] = str(exc)
        finally:
            before_png.unlink(missing_ok=True)
            after_png.unlink(missing_ok=True)

        psnr = row.get("psnr_avg")
        changed_ratio = row.get("changed_pixel_ratio")
        after_bbox = measure_subtitle_text_bbox(after, seek) if after.is_file() else {"visible": False}
        row["subtitle_bbox"] = after_bbox
        row["visible_enough"] = bool(after_bbox.get("visible"))
        sample_rows.append(row)

    result["samples"] = sample_rows
    if psnr_values:
        result["psnr_avg"] = sum(psnr_values) / len(psnr_values)
    if ratio_values:
        result["changed_pixel_ratio"] = max(ratio_values)
    result["visible_enough"] = any(row.get("visible_enough") for row in sample_rows)
    return result


def write_styled_ass_outputs(
    *,
    ass_content: str,
    publish_subtitles_dir: str | Path,
    debug_dir: str | Path | None = None,
    font_size: int | None = None,
) -> dict[str, str]:
    publish_dir = Path(publish_subtitles_dir)
    publish_dir.mkdir(parents=True, exist_ok=True)
    styled_ass = publish_dir / "subtitles_styled.ass"
    styled_ass.write_text(ass_content, encoding="utf-8")
    outputs = {"styled_ass_path": str(styled_ass.resolve())}
    if debug_dir:
        preview = Path(debug_dir) / "subtitle_style_preview.png"
        outputs["subtitle_style_preview_path"] = export_subtitle_style_preview(
            ass_content,
            preview,
            font_size=font_size,
        )
    return outputs


# Backward-compatible alias used by older validators.
MAX_FONT_SIZE = MIN_BURN_FONT_SIZE

__all__ = [
    "HIGHLIGHT_COLOURS_BGR",
    "MAX_BURN_FONT_SIZE",
    "MAX_FONT_SIZE",
    "MAX_LINES_PER_CUE",
    "MAX_SCREEN_COVERAGE_PERCENT",
    "MAX_SUBTITLE_PSNR_DB",
    "MAX_WORDS_PER_LINE",
    "MIN_BURN_FONT_SIZE",
    "PREFERRED_BURN_FONT_SIZE",
    "PLATFORM_SAFE_MARGINS",
    "POSITION_BOTTOM_CENTER",
    "POSITION_LOWER_THIRD",
    "SUBTITLE_FORMAT_VERSION",
    "ass_contains_highlight_colours",
    "break_cue_into_short_lines",
    "build_drawtext_subtitle_filter",
    "compare_subtitle_burn_visibility",
    "compute_burn_font_size",
    "compute_lower_third_margin_v",
    "export_subtitle_style_preview",
    "format_ass_content_for_burn",
    "measure_subtitle_text_bbox",
    "format_srt_content",
    "normalize_platform",
    "parse_srt_timing",
    "prepare_ass_for_burn",
    "probe_video_size",
    "resolve_srt_content",
    "validate_shorts_subtitle_cue",
    "validate_subtitle_visual_layout",
    "write_styled_ass_outputs",
]
