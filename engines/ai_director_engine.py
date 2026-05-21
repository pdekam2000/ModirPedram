import random
import json
from pathlib import Path


class AIDirectorEngine:
    def __init__(self):
        self.output_dir = Path(
            "outputs/director"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.camera_shots = [
            "extreme close-up beauty shot",
            "macro skincare texture shot",
            "cinematic side profile shot",
            "overhead skincare table shot",
            "slow cinematic push-in",
            "soft handheld beauty shot",
            "mirror reflection shot",
            "slow-motion skincare application",
            "close-up hand movement shot",
            "luxury beauty commercial framing",
        ]

        self.camera_movements = [
            "slow cinematic pan",
            "gentle handheld movement",
            "slow push forward",
            "subtle camera drift",
            "slow vertical movement",
            "cinematic floating movement",
            "soft beauty commercial motion",
        ]

        self.lighting_styles = [
            "soft bright skincare lighting",
            "warm feminine bathroom lighting",
            "luxury beauty commercial lighting",
            "soft natural morning glow",
            "clean white aesthetic lighting",
        ]

        self.emotional_pacing = [
            "calm luxurious pacing",
            "slow relaxing rhythm",
            "soft emotional beauty pacing",
            "gentle selfcare mood",
            "clean aesthetic energy",
        ]

    def build_direction_layer(
        self,
        clip_index,
    ):
        shot = random.choice(
            self.camera_shots
        )

        movement = random.choice(
            self.camera_movements
        )

        lighting = random.choice(
            self.lighting_styles
        )

        pacing = random.choice(
            self.emotional_pacing
        )

        return {
            "clip": clip_index,
            "shot": shot,
            "movement": movement,
            "lighting": lighting,
            "pacing": pacing,
        }

    def apply_direction(
        self,
        prompts,
    ):
        directed_prompts = []

        direction_data = []

        for index, prompt in enumerate(
            prompts,
            start=1,
        ):
            direction = self.build_direction_layer(
                clip_index=index
            )

            directed_prompt = f"""
DIRECTOR INSTRUCTIONS:

SHOT TYPE:
{direction['shot']}

CAMERA MOVEMENT:
{direction['movement']}

LIGHTING:
{direction['lighting']}

PACING:
{direction['pacing']}

VERY IMPORTANT:
The video must feel like a luxury
beauty commercial.

MAIN SCENE:
{prompt}
""".strip()

            directed_prompts.append(
                directed_prompt
            )

            direction_data.append(
                direction
            )

        return (
            directed_prompts,
            direction_data,
        )

    def save_direction_data(
        self,
        direction_data,
        filename="director_data.json",
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
                direction_data,
                f,
                indent=4,
                ensure_ascii=False,
            )

        return str(path)


if __name__ == "__main__":
    engine = AIDirectorEngine()

    prompts = [
        "Woman mixing yogurt and honey mask.",
        "Woman applying skincare mask softly.",
        "Woman showing glowing skin result.",
    ]

    directed_prompts, direction_data = (
        engine.apply_direction(
            prompts
        )
    )

    saved = engine.save_direction_data(
        direction_data
    )

    print("\nDIRECTED PROMPTS:\n")

    for item in directed_prompts:
        print("=" * 60)
        print(item)

    print("\nSaved direction data:")
    print(saved)