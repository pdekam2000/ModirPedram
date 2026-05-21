from dataclasses import dataclass

from engines.visual_scenario_engine import (
    VisualScenarioEngine
)


@dataclass
class SelfcarePlan:
    title: str
    hook: str
    ingredients: list
    video_prompts: list


class SelfcareContentEngine:

    def __init__(self):

        self.visual_engine = (
            VisualScenarioEngine()
        )

    def detect_content_style(
        self,
        topic
    ):

        topic_lower = topic.lower()

        if (
            "ice" in topic_lower
            or "cold" in topic_lower
            or "roller" in topic_lower
        ):
            return "ice"

        if (
            "gua sha" in topic_lower
            or "lymphatic" in topic_lower
            or "massage" in topic_lower
        ):
            return "gua_sha"

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

        if (
            "lip" in topic_lower
        ):
            return "lip"

        if (
            "scrub" in topic_lower
        ):
            return "scrub"

        return "general"

    def build_mask_video(
        self,
        topic
    ):

        style = self.detect_content_style(
            topic
        )

        visual_prompt = (
            self.visual_engine
            .build_visual_prompt(topic)
        )

        if style == "ice":
            return self.build_ice_video(
                topic,
                visual_prompt
            )

        if style == "gua_sha":
            return self.build_gua_sha_video(
                topic,
                visual_prompt
            )

        if style == "mist":
            return self.build_mist_video(
                topic,
                visual_prompt
            )

        if style == "hair":
            return self.build_hair_video(
                topic,
                visual_prompt
            )

        if style == "lip":
            return self.build_lip_video(
                topic,
                visual_prompt
            )

        if style == "scrub":
            return self.build_scrub_video(
                topic,
                visual_prompt
            )

        return self.build_general_video(
            topic,
            visual_prompt
        )

    def clip_rules(
        self,
        visual_prompt
    ):

        return f"""
{visual_prompt}

GLOBAL VIDEO RULES:
- realistic cinematic beauty quality
- avoid repetitive rubbing motions
- avoid repetitive towel scenes
- dynamic movement
- premium skincare commercial quality
- different shot composition in every clip
"""

    def build_ice_video(
        self,
        topic,
        visual_prompt
    ):

        prompts = []

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 1:
Woman opens skincare fridge and removes ice roller.
Luxury skincare setup.
Macro beauty closeups.
Fresh cinematic atmosphere.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 2:
Close-up shots of cold roller gliding under eyes.
Dynamic camera movement.
Luxury skincare commercial style.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 3:
Mirror reflection glow reveal.
Fresh healthy radiant skin.
Elegant cinematic ending.
"""
        )

        return SelfcarePlan(
            title=topic,
            hook="Morning depuff ice routine",
            ingredients=[
                "ice roller",
                "cooling facial routine",
                "morning glow"
            ],
            video_prompts=prompts
        )

    def build_gua_sha_video(
        self,
        topic,
        visual_prompt
    ):

        prompts = []

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 1:
Woman prepares luxury facial oil beside gua sha stone.
Close-up shots of glowing skincare oil.
Elegant cinematic beauty atmosphere.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 2:
Gua sha lifting routine along jawline and cheekbones.
Slow luxury beauty tracking shots.
Realistic skin texture.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 3:
Final lifted glow reveal in mirror.
Healthy luminous skin.
Premium skincare campaign feeling.
"""
        )

        return SelfcarePlan(
            title=topic,
            hook="Luxury gua sha glow ritual",
            ingredients=[
                "gua sha",
                "facial oil",
                "lymphatic massage"
            ],
            video_prompts=prompts
        )

    def build_mist_video(
        self,
        topic,
        visual_prompt
    ):

        prompts = []

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 1:
Woman fills luxury glass mist bottle.
Soft cinematic hydration visuals.
Fresh skincare atmosphere.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 2:
Slow-motion face mist spray shots.
Water droplets reflecting sunlight.
Luxury beauty commercial aesthetic.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 3:
Hydrated skin glow reveal.
Elegant feminine cinematic ending.
"""
        )

        return SelfcarePlan(
            title=topic,
            hook="Hydration glow mist routine",
            ingredients=[
                "face mist",
                "hydration",
                "fresh skincare"
            ],
            video_prompts=prompts
        )

    def build_hair_video(
        self,
        topic,
        visual_prompt
    ):

        prompts = []

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 1:
Woman prepares luxury hair oil ritual.
Elegant beauty table setup.
Warm cinematic atmosphere.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 2:
Slow-motion silky hair movement.
Hair oil applied through long healthy hair.
Luxury commercial aesthetic.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 3:
Final glossy hair reveal.
Elegant beauty campaign ending.
"""
        )

        return SelfcarePlan(
            title=topic,
            hook="Luxury silky hair ritual",
            ingredients=[
                "hair oil",
                "healthy hair",
                "silky hair"
            ],
            video_prompts=prompts
        )

    def build_lip_video(
        self,
        topic,
        visual_prompt
    ):

        prompts = []

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 1:
Luxury lip care setup with glossy lip products.
Soft feminine beauty visuals.
Close-up macro shots.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 2:
Close-up lip hydration routine.
Elegant beauty commercial movement.
Healthy glossy lips.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 3:
Final glossy lip reveal.
Luxury feminine beauty ending.
"""
        )

        return SelfcarePlan(
            title=topic,
            hook="Soft glossy lip routine",
            ingredients=[
                "lip care",
                "hydration",
                "glossy lips"
            ],
            video_prompts=prompts
        )

    def build_scrub_video(
        self,
        topic,
        visual_prompt
    ):

        prompts = []

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 1:
Luxury body scrub preparation.
Close-up texture shots.
Spa cinematic atmosphere.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 2:
Gentle body exfoliation visuals.
Luxury skincare commercial movement.
Healthy glowing skin.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 3:
Final body glow reveal.
Elegant premium selfcare ending.
"""
        )

        return SelfcarePlan(
            title=topic,
            hook="Luxury body glow routine",
            ingredients=[
                "body scrub",
                "glowing skin",
                "spa skincare"
            ],
            video_prompts=prompts
        )

    def build_general_video(
        self,
        topic,
        visual_prompt
    ):

        prompts = []

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 1:
Luxury skincare setup introduction.
Elegant beauty atmosphere.
Cinematic macro shots.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 2:
Premium skincare application sequence.
Dynamic beauty commercial camera movement.
Healthy glowing skin.
"""
        )

        prompts.append(
f"""
{self.clip_rules(visual_prompt)}

CLIP 3:
Final skincare glow reveal.
Elegant luxury beauty campaign ending.
"""
        )

        return SelfcarePlan(
            title=topic,
            hook="Luxury skincare ritual",
            ingredients=[
                "skincare",
                "beauty routine",
                "glowing skin"
            ],
            video_prompts=prompts
        )