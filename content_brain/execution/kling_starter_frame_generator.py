"""Kling Frame-to-Video Clip 1 — starter frame prompt + local image prepare (P3, no credits)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_brain.execution.kling_frame_to_video_planner import plan_kling_frame_to_video_content
from content_brain.execution.kling_native_audio_planner import KlingContentPlannerInput, _resolve_story_context

STARTER_FRAME_GENERATOR_VERSION = "kling_starter_frame_generator_p3_v1"
STARTER_FRAME_FILENAME = "frame_001.png"
STARTER_FRAME_DIRNAME = "starter_frame"
STARTER_FRAME_PROMPT_JSON = "starter_frame_prompt.json"
OUTPUT_ROOT = "kling_frame_to_video"
STARTER_IMAGE_PROMPT_MAX_CHARS = 1200
STARTER_FRAME_WIDTH = 1920
STARTER_FRAME_HEIGHT = 1080
MIN_FRAME_BYTES = 1024

TOPIC_STOP_WORDS = frozenset(
    {
        "with",
        "through",
        "during",
        "that",
        "this",
        "from",
        "their",
        "almost",
        "native",
        "audio",
        "cinematic",
        "story",
        "heavy",
        "soft",
        "into",
        "over",
        "under",
        "about",
    }
)


@dataclass
class KlingStarterFrameResult:
    ok: bool
    run_id: str
    run_dir: str
    starter_frame_path: str
    starter_image_prompt: str
    topic: str
    clip_prompt_preview: str
    frame_bytes: int = 0
    frame_is_image: bool = False
    prompt_matches_topic: bool = False
    ready_for_first_frame_upload: bool = False
    generation_mode: str = "local_pil_prepare"
    credits_spent: bool = False
    runway_generate_clicked: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STARTER_FRAME_GENERATOR_VERSION,
            "ok": self.ok,
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "starter_frame_path": self.starter_frame_path,
            "starter_image_prompt": self.starter_image_prompt,
            "topic": self.topic,
            "clip_prompt_preview": self.clip_prompt_preview,
            "frame_bytes": self.frame_bytes,
            "frame_is_image": self.frame_is_image,
            "prompt_matches_topic": self.prompt_matches_topic,
            "ready_for_first_frame_upload": self.ready_for_first_frame_upload,
            "generation_mode": self.generation_mode,
            "credits_spent": self.credits_spent,
            "runway_generate_clicked": self.runway_generate_clicked,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def create_kling_frame_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"kling_ft_{stamp}_{uuid.uuid4().hex[:8]}"


def kling_frame_run_dir(project_root: str | Path, run_id: str) -> Path:
    return Path(project_root).resolve() / "outputs" / OUTPUT_ROOT / str(run_id)


def starter_frame_dir(run_dir: str | Path) -> Path:
    path = Path(run_dir).resolve() / STARTER_FRAME_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def starter_frame_path(run_dir: str | Path) -> Path:
    return starter_frame_dir(run_dir) / STARTER_FRAME_FILENAME


def kling_frame_clip_dir(run_dir: str | Path, clip_index: int = 1) -> Path:
    path = Path(run_dir).resolve() / "clips" / f"c{int(clip_index)}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_starter_run_metadata(run_dir: str | Path) -> dict[str, Any]:
    prompt_path = starter_frame_dir(run_dir) / STARTER_FRAME_PROMPT_JSON
    if not prompt_path.is_file():
        return {}
    return json.loads(prompt_path.read_text(encoding="utf-8"))


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _topic_keywords(topic: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]{4,}", topic.lower())
    return [word for word in words if word not in TOPIC_STOP_WORDS]


def prompt_matches_topic(*, prompt: str, topic: str, min_hits: int = 2) -> bool:
    keys = _topic_keywords(topic)
    if not keys:
        return bool(_clean(prompt))
    hits = sum(1 for key in keys if key in prompt.lower())
    required = min(min_hits, max(1, len(keys)))
    return hits >= required


def build_kling_starter_image_prompt(
    *,
    topic: str,
    story_summary: str = "",
    mood: str = "",
    style: str = "",
    characters: list[str] | None = None,
    environment: str = "",
) -> tuple[str, str]:
    """Return (starter_image_prompt, clip1_prompt_preview) from Content Brain story context."""
    payload = KlingContentPlannerInput(
        topic=topic,
        story_summary=story_summary or topic,
        mood=mood,
        style=style,
        characters=list(characters or []),
        environment=environment,
        planned_duration_seconds=15,
        clip_count=1,
    )
    context = _resolve_story_context(payload)
    plan = plan_kling_frame_to_video_content(
        topic=topic,
        story_summary=story_summary or topic,
        mood=mood or context.mood,
        style=style or context.style,
        characters=characters or context.characters,
        environment=environment or context.environment,
        planned_duration_seconds=15,
        clip_count=1,
    )
    clip1 = plan.clips[0]
    cast = ", ".join(context.characters) if context.characters else "lead character"
    beat = context.beats[0] if context.beats else topic
    prompt = _clean(
        f"Cinematic hero starter frame for Kling Frame-to-Video clip 1. "
        f"Static still composition, ultra-detailed, filmic lighting, no motion blur. "
        f"Subject: {cast}. Environment: {context.environment}. "
        f"Mood: {context.mood}. Style: {context.style}. "
        f"Opening story beat: {beat}. "
        f"Camera: medium-wide hero framing with clear silhouette readability, shallow depth of field. "
        f"Continuity seed for native-audio video — this still becomes first_frame upload. "
        f"No text, subtitles, logos, watermarks, or UI overlays."
    )
    if len(prompt) > STARTER_IMAGE_PROMPT_MAX_CHARS:
        prompt = prompt[: STARTER_IMAGE_PROMPT_MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "."
    return prompt, clip1.prompt[:400]


def _render_local_starter_frame(*, output_path: Path, topic: str, mood: str) -> None:
    """Render a valid PNG locally — no Runway/Kling API, no credits."""
    from PIL import Image, ImageDraw

    width, height = STARTER_FRAME_WIDTH, STARTER_FRAME_HEIGHT
    image = Image.new("RGB", (width, height), (12, 16, 28))
    draw = ImageDraw.Draw(image)

    lowered = f"{topic} {mood}".lower()
    if any(token in lowered for token in ("neon", "rain", "city", "cyber", "robot")):
        top = (18, 24, 48)
        bottom = (90, 20, 60)
        accent = (0, 180, 255)
    elif any(token in lowered for token in ("forest", "dragon", "fantasy")):
        top = (10, 28, 18)
        bottom = (36, 58, 32)
        accent = (180, 220, 140)
    else:
        top = (20, 22, 30)
        bottom = (48, 36, 52)
        accent = (220, 180, 120)

    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)

    horizon = int(height * 0.62)
    draw.rectangle([(0, horizon), (width, height)], fill=(8, 10, 16))
    draw.ellipse([(width // 2 - 180, horizon - 260), (width // 2 + 180, horizon + 40)], fill=accent)
    draw.ellipse([(width // 2 - 90, horizon - 170), (width // 2 + 90, horizon - 10)], fill=(20, 24, 36))
    draw.line([(0, horizon), (width, horizon)], fill=(accent[0], accent[1], accent[2]), width=2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)


def _copy_reference_frame(*, source: Path, output_path: Path) -> None:
    from PIL import Image

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as img:
        rgb = img.convert("RGB")
        rgb = rgb.resize((STARTER_FRAME_WIDTH, STARTER_FRAME_HEIGHT), Image.Resampling.LANCZOS)
        rgb.save(output_path, format="PNG", optimize=True)


def is_valid_image_file(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < MIN_FRAME_BYTES:
        return False
    try:
        from PIL import Image

        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def validate_starter_frame_for_upload(
    *,
    frame_path: str | Path,
    topic: str,
    starter_image_prompt: str,
) -> tuple[bool, dict[str, bool], list[str]]:
    path = Path(frame_path).resolve()
    checks = {
        "frame_exists": path.is_file(),
        "frame_is_image": is_valid_image_file(path),
        "prompt_matches_topic": prompt_matches_topic(prompt=starter_image_prompt, topic=topic),
        "ready_for_first_frame_upload": False,
    }
    errors: list[str] = []
    if not checks["frame_exists"]:
        errors.append(f"starter frame missing: {path}")
    if not checks["frame_is_image"]:
        errors.append(f"starter frame is not a valid image: {path}")
    if not checks["prompt_matches_topic"]:
        errors.append("starter_image_prompt does not match topic keywords")
    checks["ready_for_first_frame_upload"] = all(
        checks[key] for key in ("frame_exists", "frame_is_image", "prompt_matches_topic")
    )
    return checks["ready_for_first_frame_upload"], checks, errors


def generate_kling_starter_frame(
    *,
    topic: str,
    project_root: str | Path | None = None,
    run_id: str = "",
    story_summary: str = "",
    mood: str = "",
    style: str = "",
    characters: list[str] | None = None,
    environment: str = "",
    reference_image_path: str | Path | None = None,
) -> KlingStarterFrameResult:
    root = Path(project_root or Path(__file__).resolve().parents[2])
    resolved_run_id = _clean(run_id) or create_kling_frame_run_id()
    run_dir = kling_frame_run_dir(root, resolved_run_id)
    frame_path = starter_frame_path(run_dir)
    prompt_path = starter_frame_dir(run_dir) / STARTER_FRAME_PROMPT_JSON

    starter_prompt, clip_preview = build_kling_starter_image_prompt(
        topic=topic,
        story_summary=story_summary,
        mood=mood,
        style=style,
        characters=characters,
        environment=environment,
    )

    result = KlingStarterFrameResult(
        ok=False,
        run_id=resolved_run_id,
        run_dir=str(run_dir.resolve()).replace("\\", "/"),
        starter_frame_path=str(frame_path.resolve()).replace("\\", "/"),
        starter_image_prompt=starter_prompt,
        topic=_clean(topic),
        clip_prompt_preview=clip_preview,
    )

    try:
        ref = Path(reference_image_path).resolve() if reference_image_path else None
        if ref and ref.is_file():
            _copy_reference_frame(source=ref, output_path=frame_path)
            result.generation_mode = "reference_copy_resize"
        else:
            _render_local_starter_frame(output_path=frame_path, topic=topic, mood=mood)
            result.generation_mode = "local_pil_prepare"
    except Exception as exc:
        result.errors.append(f"frame prepare failed: {exc}")
        return result

    prompt_path.write_text(
        json.dumps(
            {
                "version": STARTER_FRAME_GENERATOR_VERSION,
                "run_id": resolved_run_id,
                "topic": result.topic,
                "starter_image_prompt": starter_prompt,
                "clip_prompt_preview": clip_preview,
                "frame_path": result.starter_frame_path,
                "generation_mode": result.generation_mode,
                "credits_spent": False,
            },
            indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    ok, checks, errors = validate_starter_frame_for_upload(
        frame_path=frame_path,
        topic=topic,
        starter_image_prompt=starter_prompt,
    )
    result.frame_bytes = frame_path.stat().st_size if frame_path.is_file() else 0
    result.frame_is_image = checks["frame_is_image"]
    result.prompt_matches_topic = checks["prompt_matches_topic"]
    result.ready_for_first_frame_upload = checks["ready_for_first_frame_upload"]
    result.errors.extend(errors)
    result.ok = ok
    return result


__all__ = [
    "KlingStarterFrameResult",
    "STARTER_FRAME_GENERATOR_VERSION",
    "build_kling_starter_image_prompt",
    "create_kling_frame_run_id",
    "generate_kling_starter_frame",
    "is_valid_image_file",
    "kling_frame_run_dir",
    "kling_frame_clip_dir",
    "load_starter_run_metadata",
    "prompt_matches_topic",
    "starter_frame_path",
    "validate_starter_frame_for_upload",
]
