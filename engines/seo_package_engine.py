from pathlib import Path
import random
import json


class SEOPackageEngine:
    def __init__(self):
        self.output_dir = Path(
            "outputs/seo_packages"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.hashtags = [
            "#selfcare",
            "#skincare",
            "#glowup",
            "#beauty",
            "#reels",
            "#shorts",
            "#skincaretips",
            "#glassskin",
            "#naturalbeauty",
            "#girltips",
            "#beautyhacks",
            "#glowingskin",
            "#viralbeauty",
            "#selfcareroutine",
            "#aesthetic",
        ]

        self.ctas = [
            "Save this for your next selfcare night ✨",
            "Follow for more glow routines 💖",
            "Try this tonight and tell me the results 👀",
            "Your future skin will thank you ✨",
            "More beauty rituals coming daily 🌙",
        ]

        self.pinned_comments = [
            "Would you try this tonight? 👀",
            "Which ingredient is your favorite? ✨",
            "Saving this for my next selfcare night 💖",
            "This glow routine feels unreal 🌙",
            "Who wants more beauty rituals like this? ✨",
        ]

    def generate_title(self, topic):
        templates = [
            f"Try This {topic} Tonight ✨",
            f"This {topic} Is Going Viral 👀",
            f"The Secret Behind Better {topic} 💖",
            f"Your Skin Needs This {topic} 🌙",
            f"Stop Ignoring This {topic} Trick ✨",
        ]

        return random.choice(templates)

    def generate_description(
        self,
        topic,
        hook,
    ):
        return (
            f"{hook}\n\n"
            f"This selfcare routine focuses on {topic}.\n"
            f"Perfect for your next glow night ✨\n\n"
            f"Save this routine and follow for more beauty rituals."
        )

    def generate_hashtags(self, count=10):
        return random.sample(
            self.hashtags,
            min(count, len(self.hashtags))
        )

    def generate_keywords(self, topic):
        return [
            topic,
            "selfcare routine",
            "skincare routine",
            "beauty tips",
            "glow routine",
            "night routine",
            "viral skincare",
            "glass skin",
            "feminine aesthetic",
        ]

    def build_package(
        self,
        topic,
        hook,
        thumbnail_text,
        episode_number,
    ):
        title = self.generate_title(topic)

        description = self.generate_description(
            topic=topic,
            hook=hook,
        )

        hashtags = self.generate_hashtags()

        package = {
            "episode": episode_number,

            "title": title,

            "thumbnail_text": thumbnail_text,

            "description": description,

            "hashtags": hashtags,

            "instagram_caption": description,

            "youtube_shorts_description": description,

            "tiktok_caption": description,

            "cta": random.choice(self.ctas),

            "pinned_comment": random.choice(
                self.pinned_comments
            ),

            "keywords": self.generate_keywords(topic),
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

    package = engine.build_package(
        topic=topic,
        hook=hook,
        thumbnail_text=thumbnail_text,
        episode_number=1,
    )

    saved_file = engine.save_package(
        package=package,
        filename="episode_01_seo_package",
    )

    print("\nSEO PACKAGE CREATED\n")
    print(saved_file)