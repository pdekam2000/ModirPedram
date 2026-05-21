from dataclasses import dataclass
from typing import List


@dataclass
class SeriesVideoIdea:
    series_name: str
    episode_number: int
    category: str
    topic: str
    brand_intro: str
    hook: str


class ContentSeriesPlanner:
    def __init__(self):
        self.series_plan = [
            {
                "category": "Skin",
                "topics": [
                    "calming yogurt, honey, and oat mask for tired-looking skin",
                    "overnight glow routine for dry skin",
                    "ice facial routine for puffy morning skin",
                ],
            },
            {
                "category": "Hair",
                "topics": [
                    "simple rosemary hair rinse for shiny-looking hair",
                    "hydrating hair mask with aloe vera and yogurt",
                    "scalp massage routine for relaxing selfcare night",
                ],
            },
            {
                "category": "Eyelashes",
                "topics": [
                    "gentle lash care night routine",
                    "castor oil lash care safety tips",
                    "how to clean lashes gently before bed",
                ],
            },
            {
                "category": "Lips",
                "topics": [
                    "soft lips overnight honey routine",
                    "gentle sugar lip scrub for smooth-looking lips",
                    "dry lips rescue routine before sleep",
                ],
            },
            {
                "category": "Hands",
                "topics": [
                    "overnight hand softness routine",
                    "DIY hand mask with honey and olive oil",
                    "cuticle care routine before bed",
                ],
            },
            {
                "category": "Body Care",
                "topics": [
                    "relaxing body scrub selfcare shower routine",
                    "soft elbows and knees care routine",
                    "after-shower body oil glow routine",
                ],
            },
        ]

        self.brand_intro = (
            "Soft bright skincare setup, same elegant visual identity, "
            "clean white bathroom or vanity table, close-up of hands preparing ingredients, "
            "warm feminine selfcare mood, 5-second branded opening style."
        )

    def build_series(self) -> List[SeriesVideoIdea]:
        ideas = []
        episode = 1

        for block in self.series_plan:
            category = block["category"]

            for topic in block["topics"]:
                hook = f"Tonight's {category.lower()} selfcare ritual: {topic}."

                ideas.append(
                    SeriesVideoIdea(
                        series_name="Glow Ritual Series",
                        episode_number=episode,
                        category=category,
                        topic=topic,
                        brand_intro=self.brand_intro,
                        hook=hook,
                    )
                )

                episode += 1

        return ideas

    def get_episode(self, episode_number: int) -> SeriesVideoIdea:
        ideas = self.build_series()

        for idea in ideas:
            if idea.episode_number == episode_number:
                return idea

        raise ValueError(f"Episode {episode_number} not found.")