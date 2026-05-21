from core.selfcare_content_engine import (
    SelfcareContentEngine
)

from engines.scene_continuity_engine import (
    SceneContinuityEngine
)

from engines.ai_director_engine import (
    AIDirectorEngine
)


class VideoPromptEngine:

    def __init__(self):

        self.content_engine = (
            SelfcareContentEngine()
        )

        self.continuity_engine = (
            SceneContinuityEngine()
        )

        self.director_engine = (
            AIDirectorEngine()
        )

    def add_brand_intro(
        self,
        prompts,
        brand_intro,
    ):

        updated_prompts = []

        for index, prompt in enumerate(
            prompts,
            start=1
        ):

            if index == 1:

                updated_prompt = f"""
BRAND INTRO FIRST 5 SECONDS:
{brand_intro}

After the 5-second branded opening, continue with:

{prompt}
""".strip()

            else:

                updated_prompt = f"""
VISUAL BRAND CONSISTENCY:
Keep the same clean feminine brand identity from the opening:
{brand_intro}

{prompt}
""".strip()

            updated_prompts.append(
                updated_prompt
            )

        return updated_prompts

    def build_video_prompts(
        self,
        topic,
        brand_intro,
    ):

        plan = (
            self.content_engine
            .build_mask_video(
                topic=topic
            )
        )

        video_prompts = (
            self.add_brand_intro(
                prompts=plan.video_prompts,
                brand_intro=brand_intro,
            )
        )

        video_prompts = (
            self.continuity_engine
            .apply_continuity(
                video_prompts
            )
        )

        video_prompts, direction_data = (
            self.director_engine
            .apply_direction(
                video_prompts
            )
        )

        return {
            "video_prompts": video_prompts,
            "direction_data": direction_data,
        }