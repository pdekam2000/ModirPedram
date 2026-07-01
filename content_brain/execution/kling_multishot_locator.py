"""Stable Playwright locators for Kling Multishot controls (prefer text/role over React IDs)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from content_brain.execution.kling_multishot_config import REQUIRED_KLING_LABELS
from content_brain.execution.kling_multishot_map_loader import label_playwright_hint
from content_brain.execution.runway_ui_map_loader import _css_selector, _entry_metadata

REACT_ARIA_PATTERN = re.compile(r"react-aria\d+", re.I)
KLING_3_PRO_TEXT = re.compile(r"Kling\s+3(?:\.\d+)?(?:\s+Pro)?", re.I)

LocatorFactory = Callable[[Any], Any]


@dataclass(frozen=True)
class LocatedControl:
    label: str
    strategy: str
    locator: Any

    def css_hint(self) -> str:
        try:
            return str(self.locator.evaluate(_EXTRACT_STABLE_CSS_JS))
        except Exception:
            return ""


_EXTRACT_STABLE_CSS_JS = """(el) => {
    const tag = el.tagName.toLowerCase();
    const aria = el.getAttribute('aria-label');
    const name = el.getAttribute('name');
    const type = el.getAttribute('type');
    const ce = el.getAttribute('contenteditable');
    if (aria && ce === 'true') {
        return `${tag}[aria-label="${aria}"][contenteditable="true"]`;
    }
    if (aria) {
        return `${tag}[aria-label="${aria}"]`;
    }
    if (tag === 'input' && name && type) {
        return `input[name="${name}"][type="${type}"]`;
    }
    if (el.id && !/react-aria\\d+/i.test(el.id)) {
        return `#${CSS.escape(el.id)}`;
    }
    const text = (el.innerText || el.textContent || '').trim().slice(0, 40);
    if (text) {
        return `${tag}:has-text("${text.replace(/"/g, '\\\\"')}")`;
    }
    return tag;
}"""


def css_selector_is_unstable(css: str) -> bool:
    normalized = str(css or "").strip()
    if not normalized:
        return True
    return bool(REACT_ARIA_PATTERN.search(normalized))


def _css_from_entry(entry: dict[str, Any]) -> str:
    meta = _entry_metadata(entry)
    return _css_selector(entry, meta)


def _strategy_playwright_role_button_name(page: Any, *, name: str | re.Pattern[str]) -> Any:
    return page.get_by_role("button", name=name)


def _strategy_playwright_role_textbox_name(page: Any, *, name: str) -> Any:
    return page.get_by_role("textbox", name=name)


def _strategy_playwright_role_option_name(page: Any, *, name: str) -> Any:
    return page.get_by_role("option", name=name)


def _strategy_playwright_text_exact(page: Any, *, text: str) -> Any:
    return page.get_by_text(text, exact=True)


def _strategy_css(page: Any, *, css: str) -> Any:
    return page.locator(css)


def _read_control_text(locator: Any) -> str:
    try:
        return str(locator.inner_text(timeout=1000) or "").strip()
    except Exception:
        try:
            return str(locator.text_content(timeout=1000) or "").strip()
        except Exception:
            return ""


def _is_kling_3_pro_text(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    return bool(KLING_3_PRO_TEXT.search(normalized)) or "kling 3" in normalized.lower()


def try_locate_kling_3_pro_active(page: Any, *, timeout_ms: int = 2000) -> LocatedControl | None:
    """Find a visible Kling 3.x Pro indicator when the model is already active (picker closed)."""
    short = min(max(int(timeout_ms), 500), 3000)
    strategies: list[tuple[str, LocatorFactory]] = [
        ("role_button_kling_3_pro", lambda p: p.get_by_role("button", name=re.compile(r"Kling 3(?:\.\d+)?(?:\s+Pro)?", re.I))),
        ("text_kling_3_pro", lambda p: p.locator('button:has-text("Kling 3")')),
        ("toolbar_text_kling", lambda p: p.get_by_text(KLING_3_PRO_TEXT)),
    ]
    for strategy_name, factory in strategies:
        try:
            locator = factory(page).first
            if locator.count() <= 0 or not locator.is_visible(timeout=short):
                continue
            text = _read_control_text(locator)
            if _is_kling_3_pro_text(text):
                return LocatedControl(label="provider_kling_3_pro", strategy=strategy_name, locator=locator)
        except Exception:
            continue
    return None


def detect_kling_3_pro_current_model(page: Any, *, timeout_ms: int = 2000) -> dict[str, Any]:
    """Detect whether the Runway generate page already has Kling 3.x Pro selected."""
    short = min(max(int(timeout_ms), 500), 4000)
    out: dict[str, Any] = {
        "model_already_selected": False,
        "detected_text": "",
        "detection_method": "",
        "generate_visible": False,
        "prompt_editor_ready": False,
    }

    try:
        generate = page.get_by_role("button", name=re.compile(r"^Generate$", re.I)).first
        if generate.count() > 0 and generate.is_visible(timeout=min(1500, short)):
            out["generate_visible"] = True
    except Exception:
        pass

    for factory in (
        lambda: page.locator('[contenteditable="true"]').first,
        lambda: page.get_by_role("textbox").first,
    ):
        try:
            editor = factory()
            if editor.count() > 0 and editor.is_visible(timeout=min(1500, short)):
                out["prompt_editor_ready"] = True
                break
        except Exception:
            continue

    active = try_locate_kling_3_pro_active(page, timeout_ms=short)
    if active is not None:
        out["model_already_selected"] = True
        out["detected_text"] = _read_control_text(active.locator) or "Kling 3.0 Pro"
        out["detection_method"] = active.strategy
        return out

    if out["generate_visible"] and out["prompt_editor_ready"]:
        try:
            body = page.locator("body").inner_text(timeout=short)
            match = KLING_3_PRO_TEXT.search(body)
            if match:
                out["model_already_selected"] = True
                out["detected_text"] = match.group(0)
                out["detection_method"] = "body_text_generate_prompt_ready"
        except Exception:
            pass

    return out


def resolve_kling_3_pro_provider(
    page: Any,
    entry: dict[str, Any],
    *,
    timeout_ms: int = 8000,
) -> tuple[LocatedControl, dict[str, Any]]:
    """Resolve provider control; skip Video models picker when Kling 3.x Pro is already active."""
    detection = detect_kling_3_pro_current_model(page, timeout_ms=3000)
    if detection["model_already_selected"]:
        active = try_locate_kling_3_pro_active(page, timeout_ms=2000)
        if active is not None:
            return (
                LocatedControl(
                    label="provider_kling_3_pro",
                    strategy=f"model_already_selected:{active.strategy}",
                    locator=active.locator,
                ),
                detection,
            )
        locator = page.get_by_text(KLING_3_PRO_TEXT).first
        return (
            LocatedControl(
                label="provider_kling_3_pro",
                strategy="model_already_selected:text_probe",
                locator=locator,
            ),
            detection,
        )

    located = locate_control(page, "provider_kling_3_pro", entry, timeout_ms=timeout_ms, require_stable=False)
    return located, detection


def _build_strategies(label: str, entry: dict[str, Any]) -> list[tuple[str, LocatorFactory]]:
    css = _css_from_entry(entry)
    strategies: list[tuple[str, LocatorFactory]] = []

    if label == "provider_kling_3_pro":
        strategies.extend(
            [
                ("role_button_kling_3_pro", lambda p: _strategy_playwright_role_button_name(p, name=re.compile(r"Kling 3\.0 Pro", re.I))),
                ("text_kling_3_pro", lambda p: p.locator('button:has-text("Kling 3.0 Pro")')),
                ("role_button_video_models", lambda p: _strategy_playwright_role_button_name(p, name=re.compile(r"Video models", re.I))),
            ]
        )
    elif label == "multishot_tab":
        strategies.extend(
            [
                ("text_multishot", lambda p: _strategy_playwright_text_exact(p, text="Multishot")),
                ("label_multishot", lambda p: p.locator('label:has-text("Multishot")')),
            ]
        )
    elif label == "audio_toggle_on":
        strategies.extend(
            [
                ("role_button_audio_settings", lambda p: _strategy_playwright_role_button_name(p, name=re.compile(r"Audio settings", re.I))),
            ]
        )
    elif label == "first_frame_upload":
        strategies.extend(
            [
                ("role_button_upload", lambda p: _strategy_playwright_role_button_name(p, name=re.compile(r"Upload", re.I))),
                ("role_button_first_frame", lambda p: _strategy_playwright_role_button_name(p, name=re.compile(r"First Video Frame", re.I))),
            ]
        )
    elif label == "shot_1_prompt":
        strategies.append(("role_textbox_shot_1", lambda p: _strategy_playwright_role_textbox_name(p, name="Shot 1 prompt")))
    elif label == "shot_2_prompt":
        strategies.append(("role_textbox_shot_2", lambda p: _strategy_playwright_role_textbox_name(p, name="Shot 2 prompt")))
    elif label == "shot_1_duration_menu":
        strategies.append(("role_button_shot_duration_first", lambda p: p.get_by_role("button", name="Shot duration").first))
    elif label == "shot_1_duration_12s":
        strategies.extend(
            [
                ("role_option_12_seconds", lambda p: _strategy_playwright_role_option_name(p, name="12 seconds")),
                ("listbox_option_last", lambda p: p.locator('[role="listbox"] [role="option"]').last),
            ]
        )
    elif label == "shot_2_duration_menu":
        strategies.append(("role_button_shot_duration_nth1", lambda p: p.get_by_role("button", name="Shot duration").nth(1)))
    elif label == "shot_2_duration_3s":
        strategies.extend(
            [
                ("role_option_3_seconds", lambda p: _strategy_playwright_role_option_name(p, name="3 seconds")),
                ("listbox_option_first", lambda p: p.locator('[role="listbox"] [role="option"]').first),
            ]
        )
    elif label == "generate_button":
        strategies.extend(
            [
                ("role_button_generate", lambda p: _strategy_playwright_role_button_name(p, name=re.compile(r"^Generate$", re.I))),
                ("button_has_text_generate", lambda p: p.locator('button:has-text("Generate")')),
            ]
        )

    if css and not css_selector_is_unstable(css):
        strategies.append(("map_css_stable", lambda p, c=css: _strategy_css(p, css=c)))
    elif css:
        strategies.append(("map_css_unstable_fallback", lambda p, c=css: _strategy_css(p, css=c)))

    pw_hint = label_playwright_hint(entry)
    if pw_hint and css and not css_selector_is_unstable(css):
        strategies.append(("map_playwright_hint_css", lambda p, c=css: _strategy_css(p, css=c)))

    return strategies


def locate_control(
    page: Any,
    label: str,
    entry: dict[str, Any],
    *,
    timeout_ms: int = 8000,
    require_stable: bool = False,
) -> LocatedControl:
    if label not in REQUIRED_KLING_LABELS and label != "first_frame_upload":
        raise ValueError(f"Unsupported Kling label: {label}")

    errors: list[str] = []
    for strategy_name, factory in _build_strategies(label, entry):
        if require_stable and strategy_name in {"map_css_unstable_fallback", "map_playwright_hint"}:
            continue
        try:
            locator = factory(page).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            if locator.count() <= 0:
                errors.append(f"{strategy_name}: count=0")
                continue
            if require_stable and strategy_name == "map_css_unstable_fallback":
                errors.append(f"{strategy_name}: unstable css rejected")
                continue
            return LocatedControl(label=label, strategy=strategy_name, locator=locator)
        except Exception as exc:
            errors.append(f"{strategy_name}: {exc}")

    raise RuntimeError(f"Unable to locate {label} — tried {len(errors)} strategies: {' | '.join(errors[:4])}")


def try_locate_control(
    page: Any,
    label: str,
    entry: dict[str, Any],
    *,
    timeout_ms: int = 3000,
) -> LocatedControl | None:
    try:
        return locate_control(page, label, entry, timeout_ms=timeout_ms, require_stable=False)
    except RuntimeError:
        return None


__all__ = [
    "LocatedControl",
    "css_selector_is_unstable",
    "detect_kling_3_pro_current_model",
    "locate_control",
    "resolve_kling_3_pro_provider",
    "try_locate_control",
    "try_locate_kling_3_pro_active",
]
