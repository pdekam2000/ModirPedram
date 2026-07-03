"""Product visual diversity guard — prompt diversity, repetition gate, post-gen frame check."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

GUARD_VERSION = "product_visual_diversity_guard_v1"
VISUAL_DIVERSITY_REPORT_NAME = "visual_diversity_report.json"

PROMPT_SIMILARITY_BLOCK = 0.78
PROMPT_SIMILARITY_HIGH = 0.88
FRAME_SIMILARITY_FAIL = 0.90

STOPWORDS = frozenset(
    {
        "the",
        "and",
        "with",
        "from",
        "that",
        "this",
        "into",
        "same",
        "clip",
        "frame",
        "video",
        "motion",
        "action",
        "camera",
        "continuity",
        "seconds",
        "continuous",
        "screen",
        "preserve",
        "maintain",
        "visual",
        "style",
        "exactly",
        "via",
        "use",
        "previous",
        "last",
        "must",
        "not",
        "for",
        "next",
    }
)

CLIP_DIVERSITY_SPECS: dict[int, dict[str, str]] = {
    1: {
        "camera_distance": "wide establishing shot",
        "action_beat": "discovery and orientation — subject notices the story hook",
        "character_pose": "still or slow turn toward the inciting detail",
        "environment_detail": "introduce primary location markers and depth layers",
        "emotional_state": "curiosity and unease awakening",
        "composition": "environment-forward framing with subject entering the scene",
    },
    2: {
        "camera_distance": "medium pursuit/action shot",
        "action_beat": "escalation — motivated forward movement or investigation",
        "character_pose": "active stride, reach, or defensive reposition",
        "environment_detail": "shift parallax, weather intensity, or background activity",
        "emotional_state": "rising urgency and pressure",
        "composition": "subject off-center with leading lines into depth",
    },
    3: {
        "camera_distance": "close-up discovery/conflict",
        "action_beat": "confrontation or reveal beat — hands, object, or reaction land",
        "character_pose": "close reaction, reach, or decisive gesture",
        "environment_detail": "foreground detail or texture that supports the reveal",
        "emotional_state": "shock, conflict, or breakthrough intensity",
        "composition": "tight subject isolation with shallow depth of field",
    },
    4: {
        "camera_distance": "medium-wide or hero resolution frame",
        "action_beat": "final reveal/resolution — consequence becomes visible",
        "character_pose": "resolved stance, aftermath reaction, or payoff hold",
        "environment_detail": "contextual payoff detail without changing world identity",
        "emotional_state": "release, consequence, or emotional landing",
        "composition": "balanced hero framing with readable story outcome",
    },
    5: {
        "camera_distance": "over-shoulder or lateral medium",
        "action_beat": "aftermath progression — consequence ripples outward",
        "character_pose": "reflective pause or renewed decision",
        "environment_detail": "secondary story layer becomes readable",
        "emotional_state": "processing and renewed intent",
        "composition": "layered foreground/midground/background separation",
    },
    6: {
        "camera_distance": "slow pullback or static closing hero",
        "action_beat": "closing beat — story energy settles into final image",
        "character_pose": "final hold pose suitable for end card handoff",
        "environment_detail": "environment frames the conclusion without reset",
        "emotional_state": "closure with lingering tension or relief",
        "composition": "symmetric or wide closing composition",
    },
}


@dataclass
class SimilarClipPair:
    clip_a: int
    clip_b: int
    similarity: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_a": self.clip_a,
            "clip_b": self.clip_b,
            "similarity": round(self.similarity, 4),
            "reason": self.reason,
        }


@dataclass
class VisualDiversityReport:
    visual_diversity_score: int
    repetition_risk: str
    similar_clip_pairs: list[SimilarClipPair] = field(default_factory=list)
    blocked: bool = False
    status: str = "passed"
    publish_ready: bool = True
    youtube_upload_allowed: bool = True
    repeated_clip_warning: bool = False
    clip_prompt_axes: list[dict[str, str]] = field(default_factory=list)
    frame_similarity_pairs: list[SimilarClipPair] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": GUARD_VERSION,
            "visual_diversity_score": self.visual_diversity_score,
            "repetition_risk": self.repetition_risk,
            "similar_clip_pairs": [item.to_dict() for item in self.similar_clip_pairs],
            "frame_similarity_pairs": [item.to_dict() for item in self.frame_similarity_pairs],
            "blocked": self.blocked,
            "status": self.status,
            "publish_ready": self.publish_ready,
            "youtube_upload_allowed": self.youtube_upload_allowed,
            "repeated_clip_warning": self.repeated_clip_warning,
            "clip_prompt_axes": list(self.clip_prompt_axes),
            "metadata": dict(self.metadata),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


def _clip_spec(clip_index: int, clip_count: int) -> dict[str, str]:
    if clip_index in CLIP_DIVERSITY_SPECS:
        return dict(CLIP_DIVERSITY_SPECS[clip_index])
    cycle = ((clip_index - 1) % 4) + 1
    spec = dict(CLIP_DIVERSITY_SPECS.get(cycle, CLIP_DIVERSITY_SPECS[1]))
    spec["action_beat"] = f"{spec['action_beat']} (clip {clip_index} of {clip_count})"
    return spec


def build_clip_diversity_directive(*, clip_index: int, clip_count: int) -> str:
    spec = _clip_spec(clip_index, clip_count)
    return (
        f"Visual diversity requirement (clip {clip_index}/{clip_count}): "
        f"camera distance = {spec['camera_distance']}; "
        f"action beat = {spec['action_beat']}; "
        f"character pose = {spec['character_pose']}; "
        f"environment detail = {spec['environment_detail']}; "
        f"emotional state = {spec['emotional_state']}; "
        f"composition = {spec['composition']}. "
        "This clip must look visually distinct from every other clip in the sequence."
    )


def build_use_frame_variation_directive(*, clip_index: int, clip_count: int) -> str:
    if clip_index <= 1:
        return (
            "Use to Video continuity: preserve character identity, color palette, and world continuity "
            "from the approved starter frame while executing the clip 1 discovery action beat."
        )
    return (
        "Use Frame continuity balance: preserve character identity, color palette, and world continuity "
        "from the previous clip last frame — but force a visibly new action, new camera angle, changed "
        f"spatial position, and clear story progress for clip {clip_index} of {clip_count}. "
        "Do not repeat the previous clip blocking, pose, or camera distance."
    )


def append_visual_diversity_rules(prompt: str, *, clip_index: int, clip_count: int, use_frame: bool = True) -> str:
    parts = [str(prompt or "").strip()]
    parts.append(build_clip_diversity_directive(clip_index=clip_index, clip_count=clip_count))
    if use_frame:
        parts.append(build_use_frame_variation_directive(clip_index=clip_index, clip_count=clip_count))
    return " ".join(part for part in parts if part).strip()


def _tokenize(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]{4,}", str(text or "").lower()))
    return {token for token in tokens if token not in STOPWORDS}


def _prompt_similarity(a: str, b: str) -> float:
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)
    if not tokens_a or not tokens_b:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    jaccard = len(tokens_a & tokens_b) / len(union)
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return max(jaccard, seq * 0.85)


def _extract_axes_from_prompt(prompt: str) -> dict[str, str]:
    lowered = str(prompt or "").lower()
    for clip_index, spec in CLIP_DIVERSITY_SPECS.items():
        if spec["camera_distance"].split()[0] in lowered:
            return {**spec, "clip_index_hint": str(clip_index)}
    return {}


def detect_prompt_repetition_risk(clip_prompts: list[str]) -> VisualDiversityReport:
    prompts = [str(item or "").strip() for item in clip_prompts if str(item or "").strip()]
    pairs: list[SimilarClipPair] = []
    max_similarity = 0.0
    for index, left in enumerate(prompts):
        for other_index in range(index + 1, len(prompts)):
            right = prompts[other_index]
            similarity = _prompt_similarity(left, right)
            max_similarity = max(max_similarity, similarity)
            if similarity >= PROMPT_SIMILARITY_BLOCK:
                pairs.append(
                    SimilarClipPair(
                        clip_a=index + 1,
                        clip_b=other_index + 1,
                        similarity=similarity,
                        reason="prompt_text_overlap",
                    )
                )

    high_pairs = [pair for pair in pairs if pair.similarity >= PROMPT_SIMILARITY_BLOCK]
    blocked = bool(high_pairs) and (
        len(high_pairs) >= max(1, len(prompts) // 3)
        or max((pair.similarity for pair in high_pairs), default=0.0) >= PROMPT_SIMILARITY_HIGH
    )
    if blocked:
        repetition_risk = "high"
        score = max(0, int(100 - (max_similarity * 100)))
    elif pairs:
        repetition_risk = "medium"
        score = max(35, int(100 - (max_similarity * 80)))
    else:
        repetition_risk = "low"
        score = max(75, int(100 - (max_similarity * 40)))

    return VisualDiversityReport(
        visual_diversity_score=score,
        repetition_risk=repetition_risk,
        similar_clip_pairs=pairs,
        blocked=blocked,
        status="prompt_repetition_blocked" if blocked else "prompt_diversity_passed",
        publish_ready=not blocked,
        youtube_upload_allowed=not blocked,
        repeated_clip_warning=bool(pairs),
        clip_prompt_axes=[_extract_axes_from_prompt(prompt) for prompt in prompts],
        metadata={"clip_count": len(prompts), "max_prompt_similarity": round(max_similarity, 4)},
    )


def run_pre_generation_diversity_gate(clip_prompts: list[str]) -> dict[str, Any]:
    report = detect_prompt_repetition_risk(clip_prompts)
    payload = report.to_dict()
    payload["ok"] = not report.blocked
    if report.blocked:
        payload["error"] = "prompt_repetition_risk_high"
        payload["message"] = "Clip prompts are too similar — generation blocked before spending credits."
    return payload


def _ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def _video_duration_seconds(video_path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None or not video_path.is_file():
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
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        value = float(str(completed.stdout or "").strip())
    except ValueError:
        return None
    return value if value > 0 else None


def _extract_frame_signature(video_path: Path) -> list[float] | None:
    ffmpeg = _ffmpeg_path()
    if ffmpeg is None or not video_path.is_file() or video_path.stat().st_size <= 0:
        return None
    duration = _video_duration_seconds(video_path) or 15.0
    seek_seconds = max(0.5, duration / 2.0)
    with tempfile.TemporaryDirectory() as tmp:
        frame_path = Path(tmp) / "frame.jpg"
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{seek_seconds:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "4",
            str(frame_path),
        ]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=45)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0 or not frame_path.is_file():
            return None
        try:
            from PIL import Image
        except ImportError:
            data = frame_path.read_bytes()
            return [float(len(data) % 997), float(sum(data[:4096]) % 997)]
        image = Image.open(frame_path).convert("L").resize((16, 16))
        pixels = list(image.getdata())
        if not pixels:
            return None
        return [value / 255.0 for value in pixels]


def _signature_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    distance = sum(abs(a - b) for a, b in zip(left, right, strict=False))
    max_distance = float(len(left))
    return max(0.0, 1.0 - (distance / max_distance))


def detect_post_generation_visual_repetition(
    *,
    run_dir: str | Path,
    clip_count: int,
    prompt_report: VisualDiversityReport | None = None,
) -> VisualDiversityReport:
    run_path = Path(run_dir).resolve()
    clip_paths = [run_path / f"clip_{index}.mp4" for index in range(1, max(1, clip_count) + 1)]
    existing = [path for path in clip_paths if path.is_file() and path.stat().st_size > 0]
    base = prompt_report or VisualDiversityReport(
        visual_diversity_score=100,
        repetition_risk="low",
        status="passed",
    )

    signatures: dict[int, list[float] | None] = {}
    for index, path in enumerate(existing, start=1):
        signatures[index] = _extract_frame_signature(path)

    frame_pairs: list[SimilarClipPair] = []
    max_frame_similarity = 0.0
    indices = sorted(signatures)
    for left_index in indices:
        for right_index in indices:
            if right_index <= left_index:
                continue
            similarity = _signature_similarity(signatures[left_index], signatures[right_index])
            max_frame_similarity = max(max_frame_similarity, similarity)
            if similarity >= 0.75:
                frame_pairs.append(
                    SimilarClipPair(
                        clip_a=left_index,
                        clip_b=right_index,
                        similarity=similarity,
                        reason="mid_frame_visual_overlap",
                    )
                )

    failed = any(pair.similarity >= FRAME_SIMILARITY_FAIL for pair in frame_pairs)
    score = base.visual_diversity_score
    if failed:
        score = min(score, max(0, int(100 - (max_frame_similarity * 100))))
    elif frame_pairs:
        score = min(score, max(40, int(100 - (max_frame_similarity * 70))))

    repetition_risk = base.repetition_risk
    if failed:
        repetition_risk = "high"
    elif frame_pairs and repetition_risk == "low":
        repetition_risk = "medium"

    return VisualDiversityReport(
        visual_diversity_score=score,
        repetition_risk=repetition_risk,
        similar_clip_pairs=list(base.similar_clip_pairs) + frame_pairs,
        blocked=base.blocked or failed,
        status="visual_repetition_failed" if failed else base.status,
        publish_ready=not failed and base.publish_ready,
        youtube_upload_allowed=not failed and base.youtube_upload_allowed,
        repeated_clip_warning=bool(base.similar_clip_pairs or frame_pairs),
        clip_prompt_axes=list(base.clip_prompt_axes),
        frame_similarity_pairs=frame_pairs,
        metadata={
            **dict(base.metadata),
            "clip_paths_checked": [str(path) for path in existing],
            "max_frame_similarity": round(max_frame_similarity, 4),
            "frame_sample_mode": "mid_frame",
        },
    )


def save_visual_diversity_report(publish_or_run_dir: str | Path, report: VisualDiversityReport) -> Path:
    target_dir = Path(publish_or_run_dir).resolve()
    if target_dir.is_file():
        target_dir = target_dir.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / VISUAL_DIVERSITY_REPORT_NAME
    path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_visual_diversity_report(path_or_dir: str | Path) -> dict[str, Any] | None:
    base = Path(path_or_dir).resolve()
    candidate = base if base.name == VISUAL_DIVERSITY_REPORT_NAME else base / VISUAL_DIVERSITY_REPORT_NAME
    if not candidate.is_file():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def merge_results_visual_diversity_fields(payload: dict[str, Any], report: dict[str, Any] | None) -> dict[str, Any]:
    report = report or {}
    merged = dict(payload)
    merged["visual_diversity_score"] = int(report.get("visual_diversity_score") or 0)
    merged["visual_diversity_status"] = str(report.get("status") or "")
    merged["repetition_risk"] = str(report.get("repetition_risk") or "")
    merged["repeated_clip_warning"] = bool(report.get("repeated_clip_warning"))
    merged["similar_clip_pairs"] = list(report.get("similar_clip_pairs") or [])
    merged["frame_similarity_pairs"] = list(report.get("frame_similarity_pairs") or [])
    merged["youtube_upload_allowed"] = bool(report.get("youtube_upload_allowed", True))
    if report.get("status") == "visual_repetition_failed":
        merged["publish_ready"] = False
        merged["publish_package_ready"] = False
    return merged


__all__ = [
    "GUARD_VERSION",
    "VISUAL_DIVERSITY_REPORT_NAME",
    "VisualDiversityReport",
    "append_visual_diversity_rules",
    "build_clip_diversity_directive",
    "build_use_frame_variation_directive",
    "detect_post_generation_visual_repetition",
    "detect_prompt_repetition_risk",
    "load_visual_diversity_report",
    "merge_results_visual_diversity_fields",
    "run_pre_generation_diversity_gate",
    "save_visual_diversity_report",
]
