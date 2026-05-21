from pathlib import Path
import json
import datetime


class MasterOrchestratorEngine:
    def __init__(self):
        self.output_dir = Path(
            "outputs/orchestrator"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.pipeline = []

    def register_engine(
        self,
        engine_name,
        enabled=True,
        priority=1,
    ):
        engine = {
            "name": engine_name,
            "enabled": enabled,
            "priority": priority,
        }

        self.pipeline.append(engine)

    def build_default_pipeline(self):
        self.register_engine(
            "TrendResearchEngine",
            priority=1,
        )

        self.register_engine(
            "EpisodePlannerEngine",
            priority=2,
        )

        self.register_engine(
            "ViralHookEngine",
            priority=3,
        )

        self.register_engine(
            "SceneContinuityEngine",
            priority=4,
        )

        self.register_engine(
            "AIDirectorEngine",
            priority=5,
        )

        self.register_engine(
            "NarrationEngine",
            priority=6,
        )

        self.register_engine(
            "HailuoGenerationEngine",
            priority=7,
        )

        self.register_engine(
            "SyncEngine",
            priority=8,
        )

        self.register_engine(
            "TransitionEngine",
            priority=9,
        )

        self.register_engine(
            "SubtitleEngine",
            priority=10,
        )

        self.register_engine(
            "HookOverlayEngine",
            priority=11,
        )

        self.register_engine(
            "IngredientOverlayEngine",
            priority=12,
        )

        self.register_engine(
            "MusicEngine",
            priority=13,
        )

        self.register_engine(
            "AudioFinishEngine",
            priority=14,
        )

        self.register_engine(
            "ThumbnailEngine",
            priority=15,
        )

        self.register_engine(
            "SEOEngine",
            priority=16,
        )

        self.register_engine(
            "PerformanceAnalyzer",
            priority=17,
        )

        self.register_engine(
            "OptimizationLoopEngine",
            priority=18,
        )

    def get_pipeline(self):
        return sorted(
            self.pipeline,
            key=lambda x: x["priority"],
        )

    def build_execution_plan(
        self,
        episode_name,
    ):
        return {
            "episode": episode_name,

            "created_at": str(
                datetime.datetime.now()
            ),

            "pipeline": self.get_pipeline(),

            "mode": (
                "AUTONOMOUS_AI_MEDIA_STUDIO"
            ),
        }

    def save_execution_plan(
        self,
        plan,
        filename="execution_plan.json",
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
                plan,
                f,
                indent=4,
                ensure_ascii=False,
            )

        return str(path)


if __name__ == "__main__":
    orchestrator = (
        MasterOrchestratorEngine()
    )

    orchestrator.build_default_pipeline()

    plan = (
        orchestrator.build_execution_plan(
            episode_name=(
                "episode_01_glow_mask"
            )
        )
    )

    saved = (
        orchestrator.save_execution_plan(
            plan
        )
    )

    print("\nMASTER ORCHESTRATOR\n")

    print(json.dumps(
        plan,
        indent=4,
        ensure_ascii=False,
    ))

    print("\nSaved execution plan:")
    print(saved)