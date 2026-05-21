from dataclasses import dataclass
from typing import List


@dataclass
class TimelineSegment:
    clip_number: int
    start_time: float
    end_time: float
    scene_label: str
    narration: str
    emotion: str
    pause_after: float = 0.5


@dataclass
class VideoTimeline:
    total_duration: float
    segments: List[TimelineSegment]


class TimelineEngine:
    def build_selfcare_timeline(self) -> VideoTimeline:
        segments = [
            TimelineSegment(
                clip_number=1,
                start_time=0.0,
                end_time=9.5,
                scene_label="ingredients and mixing",
                narration=(
                    "If your skin feels tired tonight, "
                    "try this simple calming mask before bed."
                ),
                emotion="soft, warm, trustworthy",
                pause_after=0.6,
            ),
            TimelineSegment(
                clip_number=2,
                start_time=10.0,
                end_time=19.5,
                scene_label="mask application",
                narration=(
                    "Mix plain yogurt, honey, and finely ground oats. "
                    "Apply a thin layer on clean skin."
                ),
                emotion="calm, clear, educational",
                pause_after=0.6,
            ),
            TimelineSegment(
                clip_number=3,
                start_time=20.0,
                end_time=29.5,
                scene_label="rinse and finish",
                narration=(
                    "Leave it for eight to ten minutes, rinse gently, "
                    "and finish with your moisturizer."
                ),
                emotion="gentle, reassuring, elegant",
                pause_after=0.8,
            ),
        ]

        return VideoTimeline(
            total_duration=30.0,
            segments=segments,
        )