import random

from engines.cinematic_motion_engine import (
    CinematicMotionEngine
)


class VisualScenarioEngine:

    def __init__(self):

        self.motion_engine = (
            CinematicMotionEngine()
        )

        self.locations = [
            "minimal korean vanity table",
            "bright morning bedroom",
            "soft spa skincare room",
            "golden sunlight balcony",
            "modern beauty studio",
            "skincare fridge setup",
            "night selfcare candle setup",
            "minimal mirror corner",
            "luxury makeup vanity",
            "sunlit bedroom mirror",
            "soft beige dressing table",
            "modern wellness studio",
            "luxury hotel beauty suite",
            "minimal japandi beauty room",
            "editorial skincare set",
        ]

        self.outfits = [
            "black silk robe",
            "cream oversized sweater",
            "minimal beige skincare outfit",
            "luxury satin pajama",
            "minimal korean skincare outfit",
            "soft nude beauty outfit",
            "light beige linen shirt",
            "soft pink satin top",
            "elegant black beauty outfit",
            "modern clean girl fashion",
        ]

        self.lightings = [
            "soft morning sunlight",
            "golden sunrise lighting",
            "bright luxury beauty lighting",
            "soft cinematic spa lighting",
            "warm sunset glow",
            "natural window lighting",
            "moody candle spa lighting",
            "editorial beauty lighting",
            "soft diffused luxury lighting",
        ]

        self.activities = {
            "gua_sha": [
                "gua sha facial lifting",
                "lymphatic facial massage",
                "jawline sculpting routine",
                "facial contour massage",
            ],

            "ice": [
                "ice roller depuff routine",
                "cold facial massage",
                "ice bowl skin refresh",
                "cold morning glow ritual",
            ],

            "mist": [
                "hydrating face mist spray",
                "rose water facial refresh",
                "cooling hydration routine",
            ],

            "hair": [
                "luxury hair oil ritual",
                "overnight silky hair treatment",
                "scalp massage routine",
            ],

            "lip": [
                "soft lip exfoliation",
                "overnight glossy lip routine",
                "hydrating lip care",
            ],

            "general": [
                "luxury skincare application",
                "clean girl selfcare routine",
                "spa beauty ritual",
                "editorial beauty preparation",
            ],
        }

        self.moods = [
            "premium korean skincare vibe",
            "elegant spa atmosphere",
            "soft feminine beauty mood",
            "viral TikTok skincare aesthetic",
            "high-end beauty campaign",
            "modern luxury beauty editorial",
            "natural morning glow aesthetic",
            "cinematic skincare advertisement",
        ]

    def detect_style(self, topic):

        topic_lower = topic.lower()

        if (
            "gua sha" in topic_lower
            or "lymphatic" in topic_lower
            or "massage" in topic_lower
        ):
            return "gua_sha"

        if (
            "ice" in topic_lower
            or "cold" in topic_lower
            or "roller" in topic_lower
        ):
            return "ice"

        if (
            "mist" in topic_lower
            or "rose water" in topic_lower
        ):
            return "mist"

        if (
            "hair" in topic_lower
            or "oil" in topic_lower
        ):
            return "hair"

        if "lip" in topic_lower:
            return "lip"

        return "general"

    def generate_scenario(self, topic):

        style = self.detect_style(topic)

        scenario = {
            "location": random.choice(
                self.locations
            ),

            "outfit": random.choice(
                self.outfits
            ),

            "lighting": random.choice(
                self.lightings
            ),

            "activity": random.choice(
                self.activities.get(
                    style,
                    self.activities["general"]
                )
            ),

            "mood": random.choice(
                self.moods
            ),
        }

        return scenario

    def build_visual_prompt(self, topic):

        scenario = self.generate_scenario(
            topic
        )

        motion_prompt = (
            self.motion_engine
            .build_motion_prompt()
        )

        prompt = f"""
VISUAL SCENARIO:

TOPIC:
{topic}

LOCATION:
{scenario['location']}

OUTFIT:
{scenario['outfit']}

LIGHTING:
{scenario['lighting']}

ACTIVITY:
{scenario['activity']}

MOOD:
{scenario['mood']}

{motion_prompt}

MANDATORY DIVERSITY RULES:
- Every clip must feel visually different
- Avoid repeating previous skincare scenes
- Different camera framing in every clip
- Different hand movement in every clip
- Different shot composition in every clip
- Different environment feeling in every clip
- Use the selected location and outfit consistently for this video
- Use dynamic cinematic movement
- Use editorial beauty framing
- Avoid static beauty shots

STRICT NEGATIVE RULES:
- DO NOT use yogurt masks
- DO NOT use honey bowls
- DO NOT use oats
- DO NOT use white towel scenes
- DO NOT use white bathrobe scenes
- DO NOT repeat bathroom sink scenes
- DO NOT repeat generic face rubbing motions
- DO NOT generate generic skincare commercials
- DO NOT use identical female styling repeatedly
- DO NOT show mixing yogurt, honey, or oat ingredients
- DO NOT show a woman in a white towel applying a homemade mask
- DO NOT reuse previous video compositions
- DO NOT create repetitive beauty loops

VISUAL DIRECTION:
- cinematic realism
- luxury skincare campaign quality
- viral TikTok beauty aesthetic
- realistic skin texture
- realistic hands
- dynamic motion
- premium editorial beauty feeling
- visual storytelling diversity
- modern cinematic beauty direction
"""

        return prompt

    def print_example(self, topic):

        prompt = self.build_visual_prompt(
            topic
        )

        print("\n" + "=" * 60)
        print("VISUAL SCENARIO")
        print("=" * 60)

        print(prompt)


if __name__ == "__main__":

    engine = VisualScenarioEngine()

    engine.print_example(
        "Morning Gua Sha Lymphatic Facial"
    )