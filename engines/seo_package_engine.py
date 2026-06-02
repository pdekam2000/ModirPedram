from pathlib import Path
import random
import json
import re

GENERIC_HASHTAGS = [
    "#shorts",
    "#reels",
    "#viral",
    "#fyp",
    "#content",
    "#explore",
    "#video",
    "#trending",
]

GENERIC_CTAS = [
    "Save this if you found it useful.",
    "Follow for more on this topic.",
    "Share this with someone who needs it.",
    "Tell me what you think in the comments.",
    "Watch till the end for the full breakdown.",
]

GENERIC_PINNED_COMMENTS = [
    "What would you add to this?",
    "Did this match your experience?",
    "Save this for later reference.",
    "Which part was most useful?",
    "What should we cover next?",
]

SKINCARE_HASHTAGS = [
    "#selfcare",
    "#skincare",
    "#glowup",
    "#beauty",
    "#skincaretips",
    "#glassskin",
    "#naturalbeauty",
    "#beautyhacks",
    "#glowingskin",
    "#viralbeauty",
    "#selfcareroutine",
]

SKINCARE_CTAS = [
    "Save this for your next selfcare night.",
    "Follow for more glow routines.",
    "Try this tonight and tell me the results.",
    "Your future skin will thank you.",
    "More beauty rituals coming daily.",
]

SKINCARE_PINNED_COMMENTS = [
    "Would you try this tonight?",
    "Which ingredient is your favorite?",
    "Saving this for my next selfcare night.",
    "This glow routine feels unreal.",
    "Who wants more beauty rituals like this?",
]

SKINCARE_NICHE_MARKERS = ("selfcare", "skincare", "beauty")
SKINCARE_TERM_MARKERS = (
    "skin",
    "glow",
    "mask",
    "radiant",
    "hydrated",
    "beauty",
    "skincare",
    "selfcare",
    "glassskin",
)


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _tokenize_topic(topic: str) -> list[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\s'-]", " ", str(topic or "").lower())
    return [token for token in cleaned.split() if len(token) >= 3]


class SEOPackageEngine:
    def __init__(self):
        self.output_dir = Path(
            "outputs/seo_packages"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _profile_seo_keywords(self, profile):
        profile = _dict(profile)
        seo_rules = _dict(profile.get("seo_rules"))
        keywords = _list(profile.get("seo_keywords"))
        if keywords:
            return keywords
        return _list(seo_rules.get("hashtags")) or _list(seo_rules.get("keywords"))

    def _is_skincare_context(self, profile=None, topic=""):
        profile = _dict(profile)
        combined = " ".join(
            [
                str(profile.get("niche") or ""),
                str(profile.get("niche_label") or ""),
                str(topic or ""),
            ]
        ).lower()
        if any(marker in combined for marker in SKINCARE_NICHE_MARKERS):
            return True

        for keyword in self._profile_seo_keywords(profile):
            lowered = str(keyword).lower()
            if any(marker in lowered for marker in SKINCARE_NICHE_MARKERS):
                return True
        return False

    def _resolve_hashtag_pool(self, profile=None, topic=""):
        profile = _dict(profile)
        explicit = self._profile_seo_keywords(profile)
        if explicit:
            normalized = []
            for tag in explicit:
                text = str(tag).strip()
                if not text:
                    continue
                normalized.append(text if text.startswith("#") else f"#{text.replace(' ', '')}")
            if normalized:
                return normalized

        if self._is_skincare_context(profile, topic):
            return list(SKINCARE_HASHTAGS) + ["#reels", "#shorts"]

        return list(GENERIC_HASHTAGS)

    def _resolve_cta_pool(self, profile=None, topic=""):
        if self._is_skincare_context(profile, topic):
            return list(SKINCARE_CTAS)
        return list(GENERIC_CTAS)

    def _resolve_pinned_comment_pool(self, profile=None, topic=""):
        if self._is_skincare_context(profile, topic):
            return list(SKINCARE_PINNED_COMMENTS)
        return list(GENERIC_PINNED_COMMENTS)

    def generate_title(self, topic, profile=None):
        profile = _dict(profile)
        title_rules = _dict(profile.get("seo_rules"))
        templates = _list(title_rules.get("title_templates"))
        if templates:
            return random.choice(templates).format(topic=topic)

        if self._is_skincare_context(profile, topic):
            skincare_templates = [
                f"Try This {topic} Tonight",
                f"This {topic} Is Going Viral",
                f"The Secret Behind Better {topic}",
                f"Your Skin Needs This {topic}",
                f"Stop Ignoring This {topic} Trick",
            ]
            return random.choice(skincare_templates)

        generic_templates = [
            f"Why {topic} Matters Right Now",
            f"The Truth About {topic}",
            f"What Most People Miss About {topic}",
            f"{topic}: Watch Before You Decide",
            f"Stop Ignoring This {topic} Detail",
        ]
        return random.choice(generic_templates)

    def generate_description(
        self,
        topic,
        hook,
        profile=None,
    ):
        profile = _dict(profile)
        if self._is_skincare_context(profile, topic):
            return (
                f"{hook}\n\n"
                f"This selfcare routine focuses on {topic}.\n"
                f"Perfect for your next glow night.\n\n"
                f"Save this routine and follow for more beauty rituals."
            )

        return (
            f"{hook}\n\n"
            f"This video breaks down {topic} with clear, practical detail.\n"
            f"Save it if you want the full explanation.\n\n"
            f"Follow for more content on this topic."
        )

    def generate_hashtags(self, count=10, profile=None, topic=""):
        pool = self._resolve_hashtag_pool(profile=profile, topic=topic)
        return random.sample(
            pool,
            min(count, len(pool))
        )

    def generate_keywords(self, topic, profile=None):
        profile = _dict(profile)
        explicit = self._profile_seo_keywords(profile)
        if explicit:
            keywords = [str(topic).strip()] if str(topic).strip() else []
            for item in explicit:
                text = str(item).strip().lstrip("#")
                if text and text not in keywords:
                    keywords.append(text)
            return keywords

        topic_tokens = _tokenize_topic(topic)
        if self._is_skincare_context(profile, topic):
            return [
                topic,
                "selfcare routine",
                "skincare routine",
                "beauty tips",
                "glow routine",
                "night routine",
                "viral skincare",
                "glass skin",
            ]

        derived = [topic] if str(topic).strip() else []
        for token in topic_tokens[:5]:
            if token not in derived:
                derived.append(token)
        derived.extend(
            [
                f"{topic} explained" if topic else "topic explained",
                f"{topic} tips" if topic else "content tips",
                "short form video",
            ]
        )
        return derived

    def build_package(
        self,
        topic,
        hook,
        thumbnail_text,
        episode_number,
        profile=None,
    ):
        title = self.generate_title(topic, profile=profile)

        description = self.generate_description(
            topic=topic,
            hook=hook,
            profile=profile,
        )

        hashtags = self.generate_hashtags(profile=profile, topic=topic)

        package = {
            "episode": episode_number,

            "title": title,

            "thumbnail_text": thumbnail_text,

            "description": description,

            "hashtags": hashtags,

            "instagram_caption": description,

            "youtube_shorts_description": description,

            "tiktok_caption": description,

            "cta": random.choice(self._resolve_cta_pool(profile=profile, topic=topic)),

            "pinned_comment": random.choice(
                self._resolve_pinned_comment_pool(profile=profile, topic=topic)
            ),

            "keywords": self.generate_keywords(topic, profile=profile),
        }

        return package

    def save_package(
        self,
        package,
        filename,
    ):
        path = (
            self.output_dir /
            f"{filename}.json"
        )

        with open(
            path,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                package,
                f,
                indent=4,
                ensure_ascii=False,
            )

        return str(path)


if __name__ == "__main__":
    engine = SEOPackageEngine()

    topic = (
        "yogurt honey oat glow mask"
    )

    hook = (
        "Your skin looks tired because "
        "you're missing THIS."
    )

    thumbnail_text = (
        "GLOW OVERNIGHT"
    )

    skincare_profile = {
        "niche": "selfcare",
        "niche_label": "Skincare Selfcare",
    }

    package = engine.build_package(
        topic=topic,
        hook=hook,
        thumbnail_text=thumbnail_text,
        episode_number=1,
        profile=skincare_profile,
    )

    saved_file = engine.save_package(
        package=package,
        filename="episode_01_seo_package",
    )

    print("\nSEO PACKAGE CREATED\n")
    print(saved_file)
