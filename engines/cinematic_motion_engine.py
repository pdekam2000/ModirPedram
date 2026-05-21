import random


class CinematicMotionEngine:

    def __init__(self):

        self.camera_movements = [

            "slow cinematic dolly push-in",
            "soft handheld beauty movement",
            "macro cinematic skincare tracking shot",
            "slow-motion mirror reflection pan",
            "luxury beauty commercial camera drift",
            "cinematic over-the-shoulder movement",
            "slow elegant orbit camera movement",
            "soft macro push toward glowing skin",
            "high-end skincare commercial movement",
            "smooth facial tracking close-up",
            "cinematic side-profile glide shot",
            "luxury beauty editorial camera movement",
        ]

        self.transitions = [

            "soft cinematic fade transition",
            "mirror reflection transition",
            "beauty commercial light transition",
            "luxury skincare crossfade",
            "slow sunlight transition",
            "cinematic motion blur transition",
            "elegant editorial transition",
        ]

        self.shot_types = [

            "macro skincare close-up",
            "extreme close-up beauty shot",
            "mirror reflection composition",
            "over-the-shoulder skincare shot",
            "side-profile cinematic portrait",
            "beauty editorial framing",
            "luxury commercial composition",
            "dynamic handheld beauty angle",
            "cinematic facial detail shot",
        ]

        self.opening_styles = [

            "strong viral TikTok opening",
            "instant beauty transformation hook",
            "luxury skincare campaign opening",
            "clean girl aesthetic intro",
            "cinematic selfcare opening shot",
        ]

    def generate_motion_package(self):

        package = {

            "camera_movement": random.choice(
                self.camera_movements
            ),

            "transition": random.choice(
                self.transitions
            ),

            "shot_type": random.choice(
                self.shot_types
            ),

            "opening_style": random.choice(
                self.opening_styles
            ),
        }

        return package

    def build_motion_prompt(self):

        package = self.generate_motion_package()

        prompt = f"""
CINEMATIC CAMERA SYSTEM:

OPENING STYLE:
{package['opening_style']}

CAMERA MOVEMENT:
{package['camera_movement']}

SHOT TYPE:
{package['shot_type']}

TRANSITION:
{package['transition']}

RULES:
- cinematic beauty commercial quality
- dynamic movement
- avoid static framing
- avoid repetitive shot composition
- premium luxury camera feeling
- modern TikTok beauty aesthetic
- realistic cinematic motion
"""

        return prompt

    def print_example(self):

        print("\n" + "=" * 60)
        print("CINEMATIC MOTION SYSTEM")
        print("=" * 60)

        print(
            self.build_motion_prompt()
        )


if __name__ == "__main__":

    engine = CinematicMotionEngine()

    engine.print_example()