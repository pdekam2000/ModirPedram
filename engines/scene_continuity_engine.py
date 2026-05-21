import json
from pathlib import Path


class SceneContinuityEngine:
    def __init__(self):
        self.output_dir = Path(
            "outputs/continuity"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def build_global_identity(
        self,
        character_name="Soft Feminine Creator",
    ):
        return {
            "character_name": character_name,

            "gender": "female",

            "age_range": "24-32",

            "skin": (
                "soft glowing natural skin"
            ),

            "hair": (
                "long soft dark brown hair"
            ),

            "outfit": (
                "minimal white skincare robe"
            ),

            "environment": (
                "luxury clean skincare bathroom"
            ),

            "lighting": (
                "soft bright feminine lighting"
            ),

            "camera_style": (
                "cinematic beauty commercial"
            ),

            "mood": (
                "calm aesthetic luxury selfcare"
            ),

            "color_palette": (
                "soft white beige cream"
            ),
        }

    def build_continuity_prefix(
        self,
        identity,
    ):
        return f"""
CONTINUITY RULES:
Maintain the SAME woman across all clips.

Character:
- {identity['gender']}
- {identity['age_range']}
- {identity['skin']}
- {identity['hair']}
- {identity['outfit']}

Environment:
- {identity['environment']}
- {identity['lighting']}
- {identity['color_palette']}

Camera:
- {identity['camera_style']}

Mood:
- {identity['mood']}

VERY IMPORTANT:
The next clip must feel like a direct continuation
of the previous clip.
""".strip()

    def apply_continuity(
        self,
        prompts,
    ):
        identity = self.build_global_identity()

        continuity_prefix = (
            self.build_continuity_prefix(
                identity
            )
        )

        updated_prompts = []

        for index, prompt in enumerate(
            prompts,
            start=1,
        ):
            updated_prompt = f"""
{continuity_prefix}

CLIP {index}:
{prompt}
""".strip()

            updated_prompts.append(
                updated_prompt
            )

        return updated_prompts

    def save_continuity_state(
        self,
        prompts,
        filename="continuity_state.json",
    ):
        path = (
            self.output_dir /
            filename
        )

        with open(
            path,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                prompts,
                f,
                indent=4,
                ensure_ascii=False,
            )

        return str(path)


if __name__ == "__main__":
    engine = SceneContinuityEngine()

    prompts = [
        "Woman preparing yogurt and honey mask.",
        "Woman applying the mask softly.",
        "Woman showing glowing skin result.",
    ]

    updated = engine.apply_continuity(
        prompts
    )

    saved = engine.save_continuity_state(
        updated
    )

    print("\nCONTINUITY PROMPTS:\n")

    for item in updated:
        print("=" * 60)
        print(item)

    print("\nSaved continuity state:")
    print(saved)