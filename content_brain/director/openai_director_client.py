"""Director Layer — OpenAI client helper with model preference cascade."""

from __future__ import annotations

import json
import os
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[misc, assignment]

DEFAULT_MODEL_FALLBACK = "gpt-4.1-mini"
MODEL_PREFERENCE = ("gpt-5", "gpt-4.1", DEFAULT_MODEL_FALLBACK)
REQUEST_TIMEOUT_SECONDS = 90.0


def resolve_director_models() -> list[str]:
    configured = os.getenv("OPENAI_DIRECTOR_MODEL", "").strip()
    models: list[str] = []
    if configured:
        models.append(configured)
    for model in MODEL_PREFERENCE:
        if model not in models:
            models.append(model)
    return models


def openai_json_completion(
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    dry_run: bool = False,
) -> tuple[dict[str, Any], str, list[str]]:
    notes: list[str] = []
    if dry_run:
        notes.append("openai_director_dry_run")
        return {}, "", notes

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or OpenAI is None:
        notes.append("openai_client_unavailable")
        return {}, "", notes

    client = OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)
    last_error = ""
    for model in resolve_director_models():
        try:
            response = client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                temperature=0.4,
                max_tokens=3500,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                last_error = f"empty_response:{model}"
                continue
            payload = json.loads(content)
            if not isinstance(payload, dict):
                last_error = f"invalid_json_object:{model}"
                continue
            notes.append(f"openai_director_applied:{model}")
            return payload, model, notes
        except Exception as exc:  # pragma: no cover
            last_error = f"{model}:{exc}"
            continue
    notes.append(f"openai_director_failed:{last_error or 'unknown'}")
    return {}, "", notes
