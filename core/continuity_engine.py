from dataclasses import dataclass
from typing import List


@dataclass
class ClipPlan:
    clip_number: int
    duration_seconds: int
    title: str
    prompt: str


class ContinuityEngine:
    """
    Creates connected prompts for multi-clip AI video generation.
    Goal: clip2 must feel like a continuation of clip1,
    and clip3 must feel like a continuation of clip2.
    """

    def __init__(self, clip_duration: int = 10):
        self.clip_duration = clip_duration

    def build_three_clip_story(
        self,
        main_idea: str,
        visual_style: str = "dark cinematic horror, realistic, atmospheric, suspenseful",
        character: str = "same mysterious person, same face, same outfit",
        location: str = "same dark abandoned room",
        camera_style: str = "slow cinematic camera movement, handheld realism",
    ) -> List[ClipPlan]:

        shared_rules = f"""
IMPORTANT CONTINUITY RULES:
- Keep the same character: {character}
- Keep the same location: {location}
- Keep the same visual style: {visual_style}
- Keep the same lighting, mood, color grading, and atmosphere.
- Each clip must continue directly from the previous clip.
- Do not change the character identity.
- Do not suddenly change the room, outfit, face, or time of day.
- Camera style: {camera_style}
- Make it look like one continuous video, not separate clips.
"""

        clip1_prompt = f"""
{shared_rules}

CLIP 1 / OPENING:
Duration: {self.clip_duration} seconds.

Story idea:
{main_idea}

Scene:
Start with a slow cinematic establishing shot.
The character is already inside the location.
Build tension slowly.
No big reveal yet.
End the clip with a clear visual action that can continue into clip 2.

Final frame continuity:
The character turns their head toward something off-screen.
"""

        clip2_prompt = f"""
{shared_rules}

CLIP 2 / CONTINUATION:
Duration: {self.clip_duration} seconds.

Continue directly from the final frame of clip 1:
The character has just turned their head toward something off-screen.

Scene:
The camera follows the character slowly.
The tension becomes stronger.
Show more details of the same environment.
The character moves carefully toward the source of the disturbance.
Do not reveal everything yet.

Final frame continuity:
The character reaches out their hand toward a dark object or doorway.
"""

        clip3_prompt = f"""
{shared_rules}

CLIP 3 / REVEAL:
Duration: {self.clip_duration} seconds.

Continue directly from the final frame of clip 2:
The character's hand is reaching toward the dark object or doorway.

Scene:
The character touches or opens it.
The disturbing reveal happens.
Keep the reveal cinematic, realistic, and unsettling.
End with a strong final visual moment suitable for YouTube Shorts.

Final frame:
A haunting unresolved ending.
"""

        return [
            ClipPlan(
                clip_number=1,
                duration_seconds=self.clip_duration,
                title="Opening",
                prompt=clip1_prompt.strip(),
            ),
            ClipPlan(
                clip_number=2,
                duration_seconds=self.clip_duration,
                title="Continuation",
                prompt=clip2_prompt.strip(),
            ),
            ClipPlan(
                clip_number=3,
                duration_seconds=self.clip_duration,
                title="Reveal",
                prompt=clip3_prompt.strip(),
            ),
        ]