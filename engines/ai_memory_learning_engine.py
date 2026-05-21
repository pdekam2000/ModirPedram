import json
from pathlib import Path
from datetime import datetime


class AIMemoryLearningEngine:
    def __init__(self):
        self.memory_dir = Path(
            "outputs/ai_memory"
        )

        self.memory_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.memory_file = (
            self.memory_dir /
            "learning_memory.json"
        )

        self.memory = self.load_memory()

    def load_memory(self):
        if self.memory_file.exists():
            with open(
                self.memory_file,
                "r",
                encoding="utf-8",
            ) as f:
                return json.load(f)

        return {
            "videos": [],
            "best_hooks": [],
            "best_thumbnail_styles": [],
            "best_pacing": [],
            "best_caption_styles": [],
            "optimization_history": [],
        }

    def save_memory(self):
        with open(
            self.memory_file,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                self.memory,
                f,
                indent=4,
                ensure_ascii=False,
            )

    def add_video_result(
        self,
        video_name,
        topic,
        hook,
        thumbnail_text,
        score,
        rating,
    ):
        result = {
            "timestamp": str(
                datetime.now()
            ),

            "video_name": video_name,

            "topic": topic,

            "hook": hook,

            "thumbnail_text": (
                thumbnail_text
            ),

            "score": score,

            "rating": rating,
        }

        self.memory["videos"].append(
            result
        )

        if score >= 90:
            self.memory[
                "best_hooks"
            ].append(hook)

            self.memory[
                "best_thumbnail_styles"
            ].append(
                thumbnail_text
            )

        self.save_memory()

    def get_best_hooks(
        self,
        limit=10,
    ):
        hooks = (
            self.memory["best_hooks"]
        )

        return hooks[-limit:]

    def get_best_thumbnail_styles(
        self,
        limit=10,
    ):
        thumbs = (
            self.memory[
                "best_thumbnail_styles"
            ]
        )

        return thumbs[-limit:]

    def build_learning_report(self):
        total_videos = len(
            self.memory["videos"]
        )

        high_performance = [
            v
            for v in self.memory["videos"]
            if v["score"] >= 90
        ]

        average_score = 0

        if total_videos > 0:
            average_score = round(
                sum(
                    v["score"]
                    for v in self.memory["videos"]
                )
                / total_videos,
                2,
            )

        return {
            "total_videos": total_videos,

            "high_performance_videos": (
                len(high_performance)
            ),

            "average_score": average_score,

            "best_hooks": (
                self.get_best_hooks()
            ),

            "best_thumbnail_styles": (
                self.get_best_thumbnail_styles()
            ),
        }


if __name__ == "__main__":
    engine = AIMemoryLearningEngine()

    engine.add_video_result(
        video_name=(
            "episode_01_final_hooked_video.mp4"
        ),

        topic=(
            "yogurt honey oat glow mask"
        ),

        hook=(
            "Your skin looks tired "
            "because you're missing THIS."
        ),

        thumbnail_text=(
            "GLOW OVERNIGHT"
        ),

        score=92,

        rating=(
            "Excellent Shorts/Reels Potential"
        ),
    )

    report = (
        engine.build_learning_report()
    )

    print("\nAI MEMORY REPORT\n")

    print(json.dumps(
        report,
        indent=4,
        ensure_ascii=False,
    ))