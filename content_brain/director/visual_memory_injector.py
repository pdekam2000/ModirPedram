"""Inject persistent visual memory locks into clip prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.director.visual_memory_store import VisualSubjectMemory

INJECTOR_VERSION = "visual_memory_injector_v1"
MEMORY_LOCK_MARKER = "VISUAL MEMORY LOCK"


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def build_memory_lock_block(memory: VisualSubjectMemory, *, clip_index: int) -> str:
    lines = memory.identity_lock_lines()
    if clip_index == 1:
        header = (
            f"{MEMORY_LOCK_MARKER} — ESTABLISH AND FREEZE SUBJECT IDENTITY FOR ALL SUBSEQUENT CLIPS. "
            "Do not redesign subject. Do not introduce new variants. Maintain identity consistency."
        )
    else:
        header = (
            f"{MEMORY_LOCK_MARKER} — MAINTAIN EXACTLY THE SAME SUBJECT IDENTITY FROM CLIP 1. "
            "Same subject, same colors, same markings, same proportions, same appearance. "
            "Do not redesign subject. Do not introduce new variants. No species swap. No wardrobe reset."
        )
    body = " ".join(lines)
    forbidden = ""
    if memory.subject_type == "animal":
        forbidden = " Forbidden: different animal, different species, different fur pattern, different face."
    elif memory.subject_type == "object":
        forbidden = " Forbidden: different product model, different colorway, different form factor."
    return _normalize(f"{header} {body}{forbidden}")


def inject_memory_into_prompt(*, prompt: str, memory: VisualSubjectMemory, clip_index: int) -> str:
    block = build_memory_lock_block(memory, clip_index=clip_index)
    return _normalize(f"{block} {_normalize(prompt)}")


@dataclass
class VisualMemoryInjectionPlan:
    version: str = INJECTOR_VERSION
    run_id: str = ""
    memory: VisualSubjectMemory | None = None
    clip_prompts: list[str] = field(default_factory=list)
    injection_markers: list[bool] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "memory": self.memory.to_dict() if self.memory else {},
            "clip_prompts": list(self.clip_prompts),
            "injection_markers": list(self.injection_markers),
            "memory_lock_marker": MEMORY_LOCK_MARKER,
        }


def apply_visual_memory_injection(
    *,
    clip_prompts: list[str],
    memory: VisualSubjectMemory,
    run_id: str = "",
) -> VisualMemoryInjectionPlan:
    updated: list[str] = []
    markers: list[bool] = []
    for index, prompt in enumerate(clip_prompts, start=1):
        updated.append(inject_memory_into_prompt(prompt=prompt, memory=memory, clip_index=index))
        markers.append(index >= 1)
    return VisualMemoryInjectionPlan(
        run_id=run_id or memory.run_id,
        memory=memory,
        clip_prompts=updated,
        injection_markers=markers,
    )


def clip_has_memory_lock(prompt: str) -> bool:
    return MEMORY_LOCK_MARKER in str(prompt or "")


__all__ = [
    "INJECTOR_VERSION",
    "MEMORY_LOCK_MARKER",
    "VisualMemoryInjectionPlan",
    "apply_visual_memory_injection",
    "build_memory_lock_block",
    "clip_has_memory_lock",
    "inject_memory_into_prompt",
]
