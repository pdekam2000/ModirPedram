import json
from pathlib import Path
from datetime import datetime


class SEOAgent:
    """
    SEOAgent

    Purpose:
    - Generate SEO package for short-form content
    - Create:
        - SEO title
        - SEO description
        - hashtags
        - CTA
        - keyword package

    NOTE:
    - Local planning-only version
    - No AI API yet
    """

    def __init__(self):

        self.agent_name = "SEOAgent"
        self.version = "1.0"

        self.project_root = Path(__file__).resolve().parent.parent

        self.profile_path = (
            self.project_root
            / "config"
            / "content_factory_profile.json"
        )

        self.profile = self._load_profile()

    def _load_profile(self):

        if not self.profile_path.exists():
            raise FileNotFoundError(
                f"Profile not found: {self.profile_path}"
            )

        with open(
            self.profile_path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    def generate_seo_package(
        self,
        content_idea
    ):
        """
        Generate SEO package.
        """

        niche = self.profile.get(
            "default_niche",
            "General Content"
        )

        hook = content_idea.get(
            "hook",
            ""
        )

        seo_package = {

            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "agent": self.agent_name,

            "version": self.version,

            "title": self._generate_title(
                niche,
                hook
            ),

            "description": self._generate_description(
                niche,
                hook
            ),

            "hashtags": self._generate_hashtags(
                niche
            ),

            "keywords": self._generate_keywords(
                niche
            ),

            "cta": self._generate_cta()

        }

        return seo_package

    def _generate_title(
        self,
        niche,
        hook
    ):

        titles = [

            f"{hook}",

            f"{niche} Secrets Nobody Talks About",

            f"The Biggest {niche} Mistake",

            f"Viral {niche} Tips You Need To Know",

            f"This {niche} Trick Is Everywhere"

        ]

        return titles[0]

    def _generate_description(
        self,
        niche,
        hook
    ):

        description = (
            f"{hook} "
            f"Discover trending {niche} tips, "
            f"viral advice, and short-form educational content "
            f"designed for TikTok, Instagram Reels, and YouTube Shorts."
        )

        return description

    def _generate_hashtags(
        self,
        niche
    ):

        niche_clean = (
            niche
            .replace(" ", "")
            .replace("-", "")
        )

        hashtags = [

            f"#{niche_clean}",
            "#Skincare",
            "#GlowUp",
            "#BeautyTips",
            "#TikTokBeauty",
            "#Reels",
            "#Shorts",
            "#ViralVideo",
            "#Trending",
            "#SkinCareRoutine"

        ]

        return hashtags

    def _generate_keywords(
        self,
        niche
    ):

        keywords = [

            niche,
            f"{niche} tips",
            f"{niche} routine",
            f"viral {niche}",
            f"{niche} tutorial",
            f"best {niche}",
            f"{niche} shorts",
            f"{niche} hacks"

        ]

        return keywords

    def _generate_cta(self):

        ctas = [

            "Follow for more daily tips.",
            "Save this video for later.",
            "Which one surprised you most?",
            "Share this with a friend.",
            "Comment your experience below."

        ]

        return ctas[0]


if __name__ == "__main__":

    sample_idea = {

        "hook": (
            "Most people ruin their skincare "
            "without realizing it..."
        )

    }

    agent = SEOAgent()

    result = agent.generate_seo_package(
        sample_idea
    )

    print("\n=== SEO PACKAGE ===\n")

    for key, value in result.items():

        print(f"{key}:")
        print(value)
        print()