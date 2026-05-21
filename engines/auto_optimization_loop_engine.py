import json
from pathlib import Path


class AutoOptimizationLoopEngine:
    def __init__(self):
        self.output_dir = Path(
            "outputs/optimization"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def load_report(
        self,
        report_path,
    ):
        with open(
            report_path,
            "r",
            encoding="utf-8",
        ) as f:
            return json.load(f)

    def analyze_weaknesses(
        self,
        report,
    ):
        improvements = []

        if report["hook"]["score"] < 85:
            improvements.append(
                {
                    "area": "hook",
                    "action": (
                        "Use stronger curiosity "
                        "or urgency hooks."
                    ),
                }
            )

        if report["subtitles"]["score"] < 85:
            improvements.append(
                {
                    "area": "subtitles",
                    "action": (
                        "Reduce subtitle density "
                        "and increase emphasis."
                    ),
                }
            )

        if report["audio"]["score"] < 85:
            improvements.append(
                {
                    "area": "audio",
                    "action": (
                        "Lower background music "
                        "or improve narration clarity."
                    ),
                }
            )

        if (
            report["visual_consistency"]["score"]
            < 85
        ):
            improvements.append(
                {
                    "area": "visual_consistency",
                    "action": (
                        "Strengthen continuity "
                        "instructions."
                    ),
                }
            )

        if (
            report["transitions"]["score"]
            < 85
        ):
            improvements.append(
                {
                    "area": "transitions",
                    "action": (
                        "Use softer cinematic "
                        "transitions."
                    ),
                }
            )

        return improvements

    def build_optimization_strategy(
        self,
        report,
    ):
        improvements = (
            self.analyze_weaknesses(
                report
            )
        )

        strategy = {
            "video": report["video_name"],

            "overall_score": (
                report["overall_score"]
            ),

            "rating": report["rating"],

            "recommended_improvements": (
                improvements
            ),
        }

        return strategy

    def save_strategy(
        self,
        strategy,
        filename,
    ):
        path = (
            self.output_dir /
            f"{filename}.json"
        )

        with open(
            path,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                strategy,
                f,
                indent=4,
                ensure_ascii=False,
            )

        return str(path)


if __name__ == "__main__":
    engine = (
        AutoOptimizationLoopEngine()
    )

    report_path = (
        "outputs/performance_reports/"
        "episode_01_report.json"
    )

    report = engine.load_report(
        report_path
    )

    strategy = (
        engine.build_optimization_strategy(
            report
        )
    )

    saved = engine.save_strategy(
        strategy,
        filename=(
            "episode_01_optimization"
        ),
    )

    print("\nOPTIMIZATION STRATEGY\n")

    print(json.dumps(
        strategy,
        indent=4,
        ensure_ascii=False,
    ))

    print("\nSaved strategy:")
    print(saved)