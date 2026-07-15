"""AI-powered YouTube thumbnail generation — frame extract, OpenAI copy, Pillow compose."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.request import urlretrieve

from content_brain.execution.assembly_ffmpeg_availability import resolve_ffmpeg_binary

logger = logging.getLogger(__name__)

THUMBNAIL_GENERATOR_VERSION = "thumbnail_generator_v2_shorts_vertical"
THUMBNAIL_WIDTH = 1080
THUMBNAIL_HEIGHT = 1920
THUMBNAIL_SIZE = (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
TOP_ZONE_END = 400
MIDDLE_ZONE_END = 1400
MAIN_TEXT_SIZE = 90
SUB_TEXT_SIZE = 55
CHANNEL_TEXT_SIZE = 40
EMOJI_SIZE = 80
OPENAI_THUMBNAIL_MODEL = "gpt-4o-mini"
ANTON_FONT_URL = "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf"
FONT_RELATIVE_PATH = Path("project_brain") / "assets" / "fonts" / "Anton-Regular.ttf"

THUMBNAIL_SYSTEM_PROMPT = """You are a YouTube thumbnail expert.
Create SHORT, PUNCHY thumbnail text that gets clicks.
Rules:
- Max 4 words
- Use CAPS for power words
- Create curiosity gap
- Match the video topic
- Examples: 'YOU WONT BELIEVE THIS', 'SCIENCE LIED TO US',
  'THIS CHANGES EVERYTHING', 'MIND = BLOWN'
Return JSON: {
  'main_text': '3-4 word hook in CAPS',
  'sub_text': 'optional 2-3 word subtitle',
  'emoji': 'one relevant emoji',
  'bg_color': 'hex color that matches topic mood'
}"""


def _probe_video_duration(video_path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if not ffprobe:
        return None
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
        if completed.returncode != 0:
            return None
        return max(0.1, float(completed.stdout.strip()))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def _extract_frame_at(video_path: Path, timestamp_seconds: float, output_path: Path) -> bool:
    ffmpeg = resolve_ffmpeg_binary()
    if not ffmpeg:
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{max(0.0, timestamp_seconds):.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
        return completed.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _frame_score(image_path: Path) -> float:
    from PIL import Image, ImageStat

    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        stat = ImageStat.Stat(rgb)
        brightness = sum(stat.mean) / 3.0
        colorfulness = sum(stat.stddev) / 3.0
        return brightness * 0.45 + colorfulness * 0.55


def extract_best_video_frame(
    *,
    video_path: str | Path,
    output_dir: str | Path | None = None,
) -> Path | None:
    """Extract 5 frames (0%, 25%, 50%, 75%, 90%) and return the brightest/colorful one."""
    path = Path(video_path)
    if not path.is_file():
        return None

    duration = _probe_video_duration(path) or 30.0
    timestamps = [0.0, duration * 0.25, duration * 0.50, duration * 0.75, duration * 0.90]
    work_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="thumb_frames_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    best_path: Path | None = None
    best_score = -1.0
    for index, timestamp in enumerate(timestamps):
        frame_path = work_dir / f"frame_{index}.jpg"
        if not _extract_frame_at(path, timestamp, frame_path):
            continue
        score = _frame_score(frame_path)
        if score > best_score:
            best_score = score
            best_path = frame_path
    return best_path


def _ensure_anton_font(project_root: Path) -> Path | None:
    font_path = project_root / FONT_RELATIVE_PATH
    if font_path.is_file():
        return font_path
    font_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        urlretrieve(ANTON_FONT_URL, font_path)
    except Exception as exc:
        logger.warning("Could not download Anton font: %s", exc)
        font_path = None

    windows_candidates = [
        Path(r"C:\Windows\Fonts\Anton-Regular.ttf"),
        Path(r"C:\Windows\Fonts\impact.ttf"),
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
    ]
    for candidate in windows_candidates:
        if candidate.is_file():
            return candidate
    return font_path if font_path and font_path.is_file() else None


def _load_font(project_root: Path, size: int) -> Any:
    from PIL import ImageFont

    font_path = _ensure_anton_font(project_root)
    if font_path and font_path.is_file():
        try:
            return ImageFont.truetype(str(font_path), size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _parse_hex_color(value: str, fallback: str = "#FF4500") -> tuple[int, int, int]:
    text = str(value or fallback).strip()
    if not text.startswith("#"):
        text = f"#{text}"
    try:
        if len(text) == 7:
            return int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)
    except ValueError:
        pass
    return 255, 69, 0


def _openai_thumbnail_copy(*, project_root: Path, title: str) -> dict[str, str]:
    fallback = {
        "main_text": "MIND = BLOWN",
        "sub_text": "SCIENCE FACT",
        "emoji": "🧠",
        "bg_color": "#FF4500",
    }
    try:
        from content_brain.story.kling_story_first_openai_writer import get_openai_client

        client = get_openai_client(project_root=project_root)
        response = client.chat.completions.create(
            model=OPENAI_THUMBNAIL_MODEL,
            messages=[
                {"role": "system", "content": THUMBNAIL_SYSTEM_PROMPT},
                {"role": "user", "content": f"Video title: {title}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.8,
        )
        raw = (response.choices[0].message.content or "").strip()
        payload = json.loads(raw) if raw else {}
        if not isinstance(payload, dict):
            return fallback
        return {
            "main_text": str(payload.get("main_text") or fallback["main_text"]).upper()[:40],
            "sub_text": str(payload.get("sub_text") or fallback["sub_text"])[:30],
            "emoji": str(payload.get("emoji") or fallback["emoji"])[:4],
            "bg_color": str(payload.get("bg_color") or fallback["bg_color"]),
        }
    except Exception as exc:
        logger.warning("OpenAI thumbnail copy failed, using fallback: %s", exc)
        cleaned = re.sub(r"[^A-Za-z0-9 ]+", "", str(title or "")).strip()
        words = cleaned.split()[:4] or ["SCIENCE", "FACT"]
        fallback["main_text"] = " ".join(words).upper()
        return fallback


def _draw_text_with_stroke(
    draw: Any,
    *,
    position: tuple[int, int],
    text: str,
    font: Any,
    fill: tuple[int, int, int],
    stroke_fill: tuple[int, int, int] = (0, 0, 0),
    stroke_width: int = 6,
) -> None:
    x, y = position
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            if dx * dx + dy * dy <= stroke_width * stroke_width:
                draw.text((x + dx, y + dy), text, font=font, fill=stroke_fill)
    draw.text((x, y), text, font=font, fill=fill)


def _crop_to_aspect_ratio(image: Any, aspect_width: int, aspect_height: int) -> Any:
    """Center-crop image to target aspect ratio (e.g. 9:16 for Shorts)."""
    src_w, src_h = image.size
    target_ratio = aspect_width / aspect_height
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        return image.crop((left, 0, left + new_w, src_h))
    new_h = int(src_w / target_ratio)
    top = (src_h - new_h) // 2
    return image.crop((0, top, src_w, top + new_h))


def _prepare_middle_frame(source: Any) -> Any:
    """Crop to 9:16 and fit the middle video band (1080x1000)."""
    from PIL import Image

    cropped = _crop_to_aspect_ratio(source.convert("RGB"), 9, 16)
    middle_w = THUMBNAIL_WIDTH
    middle_h = MIDDLE_ZONE_END - TOP_ZONE_END
    src_w, src_h = cropped.size
    scale = max(middle_w / src_w, middle_h / src_h)
    resized = cropped.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - middle_w) // 2
    top = (resized.height - middle_h) // 2
    return resized.crop((left, top, left + middle_w, top + middle_h))


def _apply_vertical_gradients(canvas: Any) -> Any:
    """Top 30% and bottom 30% dark gradients; middle band stays clear."""
    from PIL import Image, ImageDraw

    overlay = Image.new("RGBA", THUMBNAIL_SIZE, (0, 0, 0, 0))
    gradient = ImageDraw.Draw(overlay)
    width, height = THUMBNAIL_SIZE
    top_fade_end = int(height * 0.30)
    bottom_fade_start = int(height * 0.70)
    for y in range(top_fade_end):
        alpha = int(220 * (1.0 - (y / max(top_fade_end - 1, 1))))
        gradient.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    for y in range(bottom_fade_start, height):
        alpha = int(220 * ((y - bottom_fade_start) / max(height - bottom_fade_start - 1, 1)))
        gradient.line([(0, y), (width, y)], fill=(0, 0, 0, min(220, alpha)))
    return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")


def compose_youtube_thumbnail(
    *,
    project_root: str | Path,
    frame_path: str | Path,
    title: str,
    channel_name: str = "Science That Feels Impossible",
    output_path: str | Path | None = None,
    copy: dict[str, str] | None = None,
) -> Path:
    from PIL import Image, ImageDraw, ImageFilter

    root = Path(project_root).resolve()
    frame = Path(frame_path)
    if not frame.is_file():
        raise FileNotFoundError(f"frame_missing:{frame}")

    text_copy = dict(copy or _openai_thumbnail_copy(project_root=root, title=title))
    border_color = _parse_hex_color(text_copy.get("bg_color", "#FF4500"))

    with Image.open(frame) as source:
        middle_frame = _prepare_middle_frame(source)
        middle_frame = middle_frame.filter(ImageFilter.GaussianBlur(radius=1))

    canvas = Image.new("RGB", THUMBNAIL_SIZE, (0, 0, 0))
    canvas.paste(middle_frame, (0, TOP_ZONE_END))
    canvas = _apply_vertical_gradients(canvas)

    draw = ImageDraw.Draw(canvas)
    main_font = _load_font(root, MAIN_TEXT_SIZE)
    sub_font = _load_font(root, SUB_TEXT_SIZE)
    channel_font = _load_font(root, CHANNEL_TEXT_SIZE)
    emoji_font = _load_font(root, EMOJI_SIZE)

    main_text = str(text_copy.get("main_text") or "MIND = BLOWN")
    sub_text = str(text_copy.get("sub_text") or "")
    emoji = str(text_copy.get("emoji") or "🧠")

    width, height = THUMBNAIL_SIZE
    main_bbox = draw.textbbox((0, 0), main_text, font=main_font)
    main_w = main_bbox[2] - main_bbox[0]
    main_h = main_bbox[3] - main_bbox[1]
    main_x = (width - main_w) // 2
    main_y = max(36, (TOP_ZONE_END - main_h) // 2 - 10)
    _draw_text_with_stroke(
        draw,
        position=(main_x, main_y),
        text=main_text,
        font=main_font,
        fill=(255, 255, 255),
        stroke_width=6,
    )

    if sub_text:
        sub_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
        sub_w = sub_bbox[2] - sub_bbox[0]
        sub_x = (width - sub_w) // 2
        sub_y = min(main_y + main_h + 12, TOP_ZONE_END - 56)
        _draw_text_with_stroke(
            draw,
            position=(sub_x, sub_y),
            text=sub_text,
            font=sub_font,
            fill=(255, 220, 0),
            stroke_width=4,
        )

    channel_label = str(channel_name or "Science That Feels Impossible")[:48]
    channel_bbox = draw.textbbox((0, 0), channel_label, font=channel_font)
    channel_w = channel_bbox[2] - channel_bbox[0]
    channel_x = (width - channel_w) // 2
    channel_y = MIDDLE_ZONE_END + ((height - MIDDLE_ZONE_END) // 2) - 20
    _draw_text_with_stroke(
        draw,
        position=(channel_x, channel_y),
        text=channel_label,
        font=channel_font,
        fill=(220, 220, 220),
        stroke_width=3,
    )
    draw.text((width - 96, height - 110), emoji, font=emoji_font, fill=(255, 255, 255))

    draw.rectangle([(0, 0), (width - 1, height - 1)], outline=border_color, width=2)

    if output_path:
        out = Path(output_path)
    else:
        out = root / "outputs" / "thumbnails" / f"thumb_{abs(hash(title)) % 10_000_000}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, format="JPEG", quality=92, optimize=True)
    return out


def generate_youtube_thumbnail(
    *,
    project_root: str | Path,
    video_path: str | Path,
    title: str,
    channel_name: str = "",
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Full pipeline: extract frame, OpenAI copy, compose JPEG thumbnail."""
    root = Path(project_root).resolve()
    path = Path(video_path)
    if not path.is_file():
        return {"ok": False, "reason": "video_missing"}

    frame_path = extract_best_video_frame(video_path=path)
    if frame_path is None:
        return {"ok": False, "reason": "frame_extract_failed"}

    copy = _openai_thumbnail_copy(project_root=root, title=title)
    channel = str(channel_name or "Science That Feels Impossible")
    thumbnail_path = compose_youtube_thumbnail(
        project_root=root,
        frame_path=frame_path,
        title=title,
        channel_name=channel,
        output_path=output_path,
        copy=copy,
    )
    return {
        "ok": True,
        "thumbnail_path": str(thumbnail_path.resolve()),
        "frame_path": str(frame_path.resolve()),
        "copy": copy,
        "version": THUMBNAIL_GENERATOR_VERSION,
    }


def generate_and_upload_youtube_thumbnail(
    *,
    project_root: str | Path,
    profile: dict[str, Any],
    video_path: str | Path,
    video_id: str,
    title: str,
    channel_name: str = "",
) -> dict[str, Any]:
    """Generate thumbnail and upload it to an existing YouTube video."""
    from content_brain.upload.youtube_uploader import extract_youtube_video_id, upload_thumbnail_to_youtube

    resolved_id = extract_youtube_video_id(video_id)
    if not resolved_id:
        return {"ok": False, "reason": "video_id_missing"}

    root = Path(project_root).resolve()
    output_path = root / "outputs" / "thumbnails" / f"{resolved_id}.jpg"
    generated: dict[str, Any]
    if output_path.is_file() and output_path.stat().st_size > 0 and (not video_path or not Path(video_path).is_file()):
        generated = {
            "ok": True,
            "thumbnail_path": str(output_path.resolve()),
            "copy": {},
            "reused_existing": True,
            "version": THUMBNAIL_GENERATOR_VERSION,
        }
    else:
        generated = generate_youtube_thumbnail(
            project_root=root,
            video_path=video_path,
            title=title,
            channel_name=str(channel_name or profile.get("channel_name") or "Science That Feels Impossible"),
            output_path=output_path,
        )
        if not generated.get("ok"):
            # Prefer uploading a previously generated file over failing entirely.
            if output_path.is_file() and output_path.stat().st_size > 0:
                generated = {
                    "ok": True,
                    "thumbnail_path": str(output_path.resolve()),
                    "copy": {},
                    "reused_existing": True,
                    "version": THUMBNAIL_GENERATOR_VERSION,
                }
            else:
                return generated

    thumbnail_path = str(generated.get("thumbnail_path") or "")
    upload_result = upload_thumbnail_to_youtube(
        project_root=root,
        profile=profile,
        video_id=resolved_id,
        thumbnail_path=thumbnail_path,
    )
    ok = bool(upload_result.get("ok"))
    if ok:
        logger.info("Thumbnail uploaded: %s", thumbnail_path)
    else:
        logger.warning(
            "Thumbnail generate ok but upload failed for %s: %s",
            resolved_id,
            upload_result.get("reason") or upload_result.get("details") or upload_result,
        )
    return {
        "ok": ok,
        "video_id": resolved_id,
        "thumbnail_path": thumbnail_path,
        "thumbnail_uploaded": ok,
        "copy": generated.get("copy"),
        "upload_result": upload_result,
        "version": THUMBNAIL_GENERATOR_VERSION,
    }


def maybe_generate_and_upload_youtube_thumbnail(
    *,
    project_root: str | Path,
    profile: dict[str, Any],
    video_path: str | Path,
    video_id: str,
    title: str,
) -> dict[str, Any]:
    """Best-effort thumbnail generation — never raises."""
    try:
        return generate_and_upload_youtube_thumbnail(
            project_root=project_root,
            profile=profile,
            video_path=video_path,
            video_id=video_id,
            title=title,
            channel_name=str(profile.get("channel_name") or ""),
        )
    except Exception as exc:
        logger.warning("Thumbnail generation skipped: %s", exc)
        return {"ok": False, "reason": "thumbnail_exception", "error": str(exc)}


__all__ = [
    "THUMBNAIL_GENERATOR_VERSION",
    "THUMBNAIL_WIDTH",
    "THUMBNAIL_HEIGHT",
    "THUMBNAIL_SIZE",
    "compose_youtube_thumbnail",
    "extract_best_video_frame",
    "generate_and_upload_youtube_thumbnail",
    "generate_youtube_thumbnail",
    "maybe_generate_and_upload_youtube_thumbnail",
]
