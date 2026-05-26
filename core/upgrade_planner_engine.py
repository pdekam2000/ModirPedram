from pathlib import Path
from datetime import datetime


class UpgradePlannerEngine:
    """
    Upgrade Planner Engine V1

    Purpose:
    - Build executable upgrade plans
    - Convert graph analysis into action steps
    - Produce safe implementation roadmap
    - No file modifications
    """

    def __init__(self, project_root="."):
        self.project_root = Path(project_root).resolve()

        self.brain_dir = (
            self.project_root / "project_brain"
        )

        self.output_file = (
            self.brain_dir
            / "upgrade_execution_plan.md"
        )

    # =====================================================
    # HELPERS
    # =====================================================

    def estimate_risk(
        self,
        core_files: list
    ) -> str:

        score = 0

        for file in core_files:

            lower = file.lower()

            if "main.py" in lower:
                score += 5

            if "ui/app.py" in lower:
                score += 5

            if "pipeline" in lower:
                score += 4

            if "provider" in lower:
                score += 3

            if "router" in lower:
                score += 3

            if "orchestrator" in lower:
                score += 3

        if score >= 15:
            return "CRITICAL"

        if score >= 10:
            return "HIGH"

        if score >= 5:
            return "MEDIUM"

        return "LOW"

    # =====================================================
    # PLAN GENERATION
    # =====================================================

    def create_plan(
        self,
        goal: str,
        core_files: list,
        impact_files: list
    ) -> str:

        risk = self.estimate_risk(
            core_files
        )

        lines = []

        lines.append(
            "# UPGRADE EXECUTION PLAN"
        )

        lines.append("")

        lines.append(
            f"Generated at: "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        lines.append("")
        lines.append("## Goal")
        lines.append("")
        lines.append(goal)
        lines.append("")

        lines.append("## Risk")
        lines.append("")
        lines.append(risk)
        lines.append("")

        lines.append("## Core Files")
        lines.append("")

        if core_files:
            for file in core_files:
                lines.append(
                    f"- {file}"
                )
        else:
            lines.append(
                "- None detected"
            )

        lines.append("")

        lines.append("## Impact Files")
        lines.append("")

        if impact_files:
            for file in impact_files:
                lines.append(
                    f"- {file}"
                )
        else:
            lines.append(
                "- None detected"
            )

        lines.append("")

        lines.append(
            "## Recommended Upgrade Steps"
        )

        lines.append("")

        steps = [
            "Review target files",
            "Review impact chain",
            "Create backup",
            "Implement minimal change",
            "Run verifier",
            "Run dependency graph",
            "Update project brain",
            "Generate new handoff",
        ]

        for index, step in enumerate(
            steps,
            start=1
        ):
            lines.append(
                f"{index}. {step}"
            )

        lines.append("")
        lines.append(
            "## Approval Status"
        )
        lines.append("")
        lines.append(
            "WAITING FOR USER APPROVAL"
        )

        return "\n".join(lines)

    # =====================================================
    # SAVE
    # =====================================================

    def save_plan(
        self,
        plan: str
    ) -> str:

        self.brain_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.output_file.write_text(
            plan,
            encoding="utf-8"
        )

        return str(
            self.output_file
        )

    # =====================================================
    # RUN
    # =====================================================

    def run(
        self,
        goal: str,
        core_files: list,
        impact_files: list
    ) -> str:

        print("")
        print("=" * 60)
        print(
            "MODIRAGENT UPGRADE PLANNER"
        )
        print("=" * 60)

        plan = self.create_plan(
            goal=goal,
            core_files=core_files,
            impact_files=impact_files
        )

        output = self.save_plan(
            plan
        )

        print("")
        print(
            f"Plan saved to: {output}"
        )
        print("")

        return output


if __name__ == "__main__":

    planner = UpgradePlannerEngine(
        "."
    )

    planner.run(
        goal="Upgrade video provider system",
        core_files=[
            "core/video_provider_router.py",
            "providers/runway_video_provider.py",
        ],
        impact_files=[
            "engines/video_generation_engine.py",
            "pipelines/full_video_pipeline.py",
        ],
    )