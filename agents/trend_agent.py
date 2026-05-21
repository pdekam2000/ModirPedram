import json
from pathlib import Path
from datetime import datetime


class TrendAgent:
    """
    TrendAgent

    Purpose:
    - Generate trending/viral content directions
    - Read niche/settings from config profile
    - Prepare structured AI Content Factory outputs

    NOTE:
    - No web access yet
    - No API calls yet
    - Local planning-only version
    """

    def __init__(self):

        self.agent_name = "TrendAgent"
        self.version = "2.0"

        self.project_root = Path(__file__).resolve().parent.parent

        self.profile_path = (
            self.project_root
            / "config"
            / "content_factory_profile.json"
        )

        self.profile = self._load_profile()

    def _load_profile(self):
        """
        Load Content Factory profile.
        """

        if not self.profile_path.exists():
            raise FileNotFoundError(
                f"Profile not found: {self.profile_path}"
            )

        with open(self.profile_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def generate_trend_report(self):
        """
        Generate trend report using config profile.
        """

        niche = self.profile.get(
            "default_niche",
            "General Content"
        )

        report = {
            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "agent": self.agent_name,
            "version": self.version,
            "project_name": self.profile.get(
                "project_name"
            ),
            "niche": niche,
            "language": self.profile.get(
                "language"
            ),
            "target_platforms": self.profile.get(
                "target_platforms",
                []
            ),
            "content_style": self.profile.get(
                "content_style",
                {}
            ),
            "ideas": self._generate_ideas(niche)
        }

        return report

    def _generate_ideas(self, niche):
        """
        Generate structured viral ideas.
        """

        ideas = []

        templates = [
            {
                "type": "problem_solution",
                "hook": f"Stop doing this if you want better {niche} results...",
                "angle": "Problem and solution"
            },
            {
                "type": "mistake_based",
                "hook": f"Most people ruin their {niche} without realizing it...",
                "angle": "Common mistakes"
            },
            {
                "type": "quick_tip",
                "hook": f"This 10-second {niche} trick changes everything...",
                "angle": "Fast value and curiosity"
            },
            {
                "type": "before_after",
                "hook": f"Why does this {niche} routine work so well?",
                "angle": "Transformation and proof"
            },
            {
                "type": "viral_question",
                "hook": f"Would you try this {niche} method?",
                "angle": "Comments and engagement"
            }
        ]

        for index, template in enumerate(
            templates,
            start=1
        ):

            idea = {
                "idea_id": index,
                "content_type": template["type"],
                "hook": template["hook"],
                "viral_angle": template["angle"],
                "target_platforms": self.profile.get(
                    "target_platforms",
                    []
                ),
                "seo_keywords": self._generate_keywords(
                    niche
                ),
                "audience": self.profile.get(
                    "content_style",
                    {}
                ).get(
                    "audience",
                    "General audience"
                ),
                "video_style": self.profile.get(
                    "content_style",
                    {}
                ).get(
                    "visual_style",
                    ""
                )
            }

            ideas.append(idea)

        return ideas

    def _generate_keywords(self, niche):
        """
        Generate SEO keywords.
        """

        keywords = [
            niche,
            f"{niche} tips",
            f"{niche} shorts",
            f"viral {niche}",
            f"{niche} routine",
            f"{niche} tutorial",
            f"best {niche}",
            f"{niche} hacks",
            f"{niche} glow up",
            f"trending {niche}"
        ]

        return keywords


if __name__ == "__main__":

    agent = TrendAgent()

    report = agent.generate_trend_report()

    print("\n=== TREND REPORT ===\n")

    print(
        f"Project: {report['project_name']}"
    )

    print(
        f"Niche: {report['niche']}"
    )

    print(
        f"Language: {report['language']}"
    )

    print("\n=== IDEAS ===\n")

    for idea in report["ideas"]:

        print(
            f"[{idea['idea_id']}] "
            f"{idea['hook']}"
        )

        print(
            f"Angle: {idea['viral_angle']}"
        )

        print(
            f"Audience: {idea['audience']}"
        )

        print(
            f"Style: {idea['video_style']}"
        )

        print("-" * 50)
        