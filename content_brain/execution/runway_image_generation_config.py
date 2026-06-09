"""
Runway starter image generation defaults, profiles, and mapped control resolution.

Mapping/runtime configuration only — does not change approval gates or Generate clicks.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_IMAGE_COUNT = 1
DEFAULT_IMAGE_QUALITY = "2K"
DEFAULT_IMAGE_ASPECT_RATIO = "9:16"

IMAGE_GENERATION_PROFILE_FAST_TEST = "FAST_TEST"
IMAGE_GENERATION_PROFILE_STANDARD = "STANDARD"
IMAGE_GENERATION_PROFILE_PREMIUM = "PREMIUM"

SUPPORTED_IMAGE_QUALITIES: tuple[str, ...] = ("1K", "2K", "4K")
SUPPORTED_IMAGE_COUNTS: tuple[int, ...] = (1, 4)

IMAGE_QUALITY_MENU_KEY = "image_quality_menu"
IMAGE_COUNT_MENU_KEY = "image_count_menu"
IMAGE_ASPECT_MENU_KEY = "image_aspect_ratio_menu"

IMAGE_QUALITY_CONTROL_BY_VALUE: dict[str, str] = {
    "1K": "image_quality_1k",
    "2K": "image_quality_2k",
    "4K": "image_quality_4k",
}

IMAGE_COUNT_CONTROL_BY_VALUE: dict[int, str] = {
    1: "image_count_1",
    4: "image_count_4",
}

# Image-generation aspect defaults resolve to image_aspect_ratio_9_16 (video uses aspect_ratio_9_16).
IMAGE_ASPECT_CONTROL_BY_VALUE: dict[str, str] = {
    "9:16": "image_aspect_ratio_9_16",
}

IMAGE_QUALITY_MENU_TEXTS: dict[str, tuple[str, ...]] = {
    "1K": ("1K", "1k", "1 K"),
    "2K": ("2K", "2k", "2 K"),
    "4K": ("4K", "4k", "4 K"),
}

IMAGE_COUNT_MENU_TEXTS: dict[int, tuple[str, ...]] = {
    1: ("1",),
    4: ("4",),
}


@dataclass(frozen=True)
class RunwayImageGenerationSettings:
    image_count: int = DEFAULT_IMAGE_COUNT
    image_quality: str = DEFAULT_IMAGE_QUALITY
    aspect_ratio: str = DEFAULT_IMAGE_ASPECT_RATIO

    def to_dict(self) -> dict[str, int | str]:
        return {
            "image_count": self.image_count,
            "image_quality": self.normalized_quality(),
            "aspect_ratio": self.aspect_ratio,
        }

    def normalized_quality(self) -> str:
        return normalize_image_quality(self.image_quality)

    def normalized_count(self) -> int:
        return normalize_image_count(self.image_count)


IMAGE_GENERATION_PROFILES: dict[str, RunwayImageGenerationSettings] = {
    IMAGE_GENERATION_PROFILE_FAST_TEST: RunwayImageGenerationSettings(
        image_count=1,
        image_quality="1K",
    ),
    IMAGE_GENERATION_PROFILE_STANDARD: RunwayImageGenerationSettings(
        image_count=1,
        image_quality="2K",
    ),
    IMAGE_GENERATION_PROFILE_PREMIUM: RunwayImageGenerationSettings(
        image_count=1,
        image_quality="4K",
    ),
}


def default_image_generation_settings() -> RunwayImageGenerationSettings:
    return RunwayImageGenerationSettings()


def normalize_image_quality(value: str) -> str:
    cleaned = str(value or "").strip().upper().replace(" ", "")
    if cleaned in IMAGE_QUALITY_CONTROL_BY_VALUE:
        return cleaned
    raise ValueError(
        f"unsupported image quality: {value!r} "
        f"(supported: {', '.join(SUPPORTED_IMAGE_QUALITIES)})"
    )


def normalize_image_count(value: int | str) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"unsupported image count: {value!r}") from exc
    if count not in IMAGE_COUNT_CONTROL_BY_VALUE:
        raise ValueError(
            f"unsupported image count: {count} "
            f"(supported: {', '.join(str(item) for item in SUPPORTED_IMAGE_COUNTS)})"
        )
    return count


def resolve_image_generation_profile(name: str) -> RunwayImageGenerationSettings:
    key = str(name or "").strip().upper()
    profile = IMAGE_GENERATION_PROFILES.get(key)
    if profile is None:
        supported = ", ".join(sorted(IMAGE_GENERATION_PROFILES))
        raise ValueError(f"unknown image generation profile: {name!r} (supported: {supported})")
    return profile


def image_quality_control_key(quality: str) -> str:
    normalized = normalize_image_quality(quality)
    return IMAGE_QUALITY_CONTROL_BY_VALUE[normalized]


def image_count_control_key(count: int | str) -> str:
    normalized = normalize_image_count(count)
    return IMAGE_COUNT_CONTROL_BY_VALUE[normalized]


def image_aspect_control_key(aspect_ratio: str = DEFAULT_IMAGE_ASPECT_RATIO) -> str:
    key = str(aspect_ratio or "").strip()
    control = IMAGE_ASPECT_CONTROL_BY_VALUE.get(key)
    if control is None:
        supported = ", ".join(sorted(IMAGE_ASPECT_CONTROL_BY_VALUE))
        raise ValueError(f"unsupported image aspect ratio: {aspect_ratio!r} (supported: {supported})")
    return control


def menu_option_texts_for_image_quality(quality: str) -> tuple[str, ...]:
    normalized = normalize_image_quality(quality)
    return IMAGE_QUALITY_MENU_TEXTS[normalized]


def menu_option_texts_for_image_count(count: int | str) -> tuple[str, ...]:
    normalized = normalize_image_count(count)
    return IMAGE_COUNT_MENU_TEXTS[normalized]


__all__ = [
    "DEFAULT_IMAGE_ASPECT_RATIO",
    "DEFAULT_IMAGE_COUNT",
    "DEFAULT_IMAGE_QUALITY",
    "IMAGE_ASPECT_CONTROL_BY_VALUE",
    "IMAGE_ASPECT_MENU_KEY",
    "IMAGE_COUNT_CONTROL_BY_VALUE",
    "IMAGE_COUNT_MENU_KEY",
    "IMAGE_COUNT_MENU_TEXTS",
    "IMAGE_GENERATION_PROFILES",
    "IMAGE_GENERATION_PROFILE_FAST_TEST",
    "IMAGE_GENERATION_PROFILE_PREMIUM",
    "IMAGE_GENERATION_PROFILE_STANDARD",
    "IMAGE_QUALITY_CONTROL_BY_VALUE",
    "IMAGE_QUALITY_MENU_KEY",
    "IMAGE_QUALITY_MENU_TEXTS",
    "RunwayImageGenerationSettings",
    "SUPPORTED_IMAGE_COUNTS",
    "SUPPORTED_IMAGE_QUALITIES",
    "default_image_generation_settings",
    "image_aspect_control_key",
    "image_count_control_key",
    "image_quality_control_key",
    "menu_option_texts_for_image_count",
    "menu_option_texts_for_image_quality",
    "normalize_image_count",
    "normalize_image_quality",
    "resolve_image_generation_profile",
]
