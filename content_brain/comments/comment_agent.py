"""Comment agent foundation — draft replies only, no auto-posting."""

from __future__ import annotations

import json
import os
import re
from typing import Any

COMMENT_AGENT_VERSION = "comment_agent_v1"

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"


def _rule_based_reply(*, comment_text: str, topic: str, tone: str, language: str) -> dict[str, Any]:
    cleaned = " ".join(str(comment_text or "").split()).strip()
    topic_text = str(topic or "this video").strip()
    tone_text = str(tone or "friendly").strip().lower()
    if not cleaned:
        return {
            "suggested_reply": "",
            "risk_level": RISK_HIGH,
            "approve_required": True,
            "notes": "Empty comment text.",
            "source": "rule_based",
        }

    if re.search(r"(hate|stupid|scam|idiot|kill|attack)", cleaned, re.I):
        return {
            "suggested_reply": "Thanks for sharing your perspective. We keep this channel respectful and focused on helpful content.",
            "risk_level": RISK_HIGH,
            "approve_required": True,
            "notes": "Potentially hostile comment detected.",
            "source": "rule_based",
        }

    if "?" in cleaned:
        reply = f"Great question about {topic_text}. We cover that in more detail in upcoming videos — thanks for watching!"
    elif tone_text in {"cinematic", "professional", "formal"}:
        reply = f"Thank you for watching. We appreciate your interest in {topic_text}."
    else:
        reply = f"Thanks for the comment! Glad {topic_text} was useful — more coming soon."

    return {
        "suggested_reply": reply,
        "risk_level": RISK_LOW,
        "approve_required": True,
        "notes": "Draft only — posting requires approval.",
        "source": "rule_based",
    }


def draft_comment_reply(
    *,
    comment_text: str,
    video_topic: str = "",
    channel_tone: str = "friendly",
    language: str = "English",
    use_openai: bool = True,
) -> dict[str, Any]:
    base = _rule_based_reply(
        comment_text=comment_text,
        topic=video_topic,
        tone=channel_tone,
        language=language,
    )
    payload = {
        "version": COMMENT_AGENT_VERSION,
        "comment_text": str(comment_text or ""),
        "video_topic": str(video_topic or ""),
        "channel_tone": str(channel_tone or "friendly"),
        "language": str(language or "English"),
        "suggested_reply": base["suggested_reply"],
        "risk_level": base["risk_level"],
        "approve_required": True,
        "auto_posted": False,
        "notes": base["notes"],
        "source": base["source"],
    }

    if not use_openai:
        return payload

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        payload["notes"] = "OpenAI unavailable — rule-based draft used."
        return payload

    try:
        from openai import OpenAI
    except ImportError:
        payload["notes"] = "OpenAI package unavailable — rule-based draft used."
        return payload

    prompt = {
        "comment_text": comment_text,
        "video_topic": video_topic,
        "channel_tone": channel_tone,
        "language": language,
        "constraints": [
            "Draft only, do not claim anything was posted.",
            "Keep reply short and platform-safe.",
            "Return JSON with suggested_reply, risk_level, notes.",
        ],
    }
    try:
        client = OpenAI(api_key=api_key, timeout=30.0)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You draft social video comment replies. Never auto-post. Always set approve_required=true.",
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            temperature=0.3,
            max_tokens=250,
        )
        raw = (response.choices[0].message.content or "").strip()
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and parsed.get("suggested_reply"):
            payload["suggested_reply"] = str(parsed.get("suggested_reply") or "").strip()
            payload["risk_level"] = str(parsed.get("risk_level") or RISK_MEDIUM)
            payload["notes"] = str(parsed.get("notes") or "OpenAI draft generated.")
            payload["source"] = "openai"
    except Exception as exc:
        payload["notes"] = f"OpenAI draft fallback: {exc}"

    payload["approve_required"] = True
    payload["auto_posted"] = False
    return payload


def draft_pinned_comments_from_metadata(metadata_bundle: dict[str, Any]) -> dict[str, Any]:
    platforms = dict(metadata_bundle.get("platforms") or {})
    drafts: dict[str, str] = {}
    for platform, meta in platforms.items():
        if not isinstance(meta, dict):
            continue
        pinned = str(meta.get("pinned_comment") or "").strip()
        if not pinned:
            pinned = f"Thanks for watching! Tell us what you think about {metadata_bundle.get('video_topic', 'this video')}."
        drafts[str(platform)] = pinned
    return {
        "version": COMMENT_AGENT_VERSION,
        "video_topic": str(metadata_bundle.get("video_topic") or ""),
        "pinned_comments": drafts,
        "auto_posted": False,
        "approve_required": True,
        "source": "metadata_agent",
    }


__all__ = ["COMMENT_AGENT_VERSION", "draft_comment_reply", "draft_pinned_comments_from_metadata"]
