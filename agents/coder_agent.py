from datetime import datetime
from pathlib import Path


class CoderAgent:
    """
    Safe Coder Agent V1

    Purpose:
    - Understand requested coding changes
    - Read project brain context
    - Produce a safe coding plan
    - DO NOT edit files automatically yet
    """

    def __init__(self, project_root="."):
        self.project_root = Path(project_root).resolve()

        self.brain_dir = (
            self.project_root / "project_brain"
        )

    def read_brain_file(self, filename: str) -> str:
        path = self.brain_dir / filename

        if not path.exists():
            return ""

        return path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    def analyze_request(self, user_goal: str) -> str:
        current_state = self.read_brain_file(
            "current_state.md"
        )

        dependency_map = self.read_brain_file(
            "dependency_map.md"
        )

        pipeline_map = self.read_brain_file(
            "pipeline_map.md"
        )

        file_ownership = self.read_brain_file(
            "file_ownership.md"
        )

        impact_report = self.read_brain_file(
            "impact_report.md"
        )

        lines = []

        lines.append("# CODER AGENT PLAN")
        lines.append("")

        lines.append(
            f"Generated at: "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        lines.append("")

        lines.append("## User Goal")
        lines.append(user_goal)

        lines.append("")
        lines.append("## Safety Mode")

        lines.append(
            "- Automatic file editing: DISABLED"
        )

        lines.append(
            "- Risky changes require backup"
        )

        lines.append(
            "- main.py should stay minimal"
        )

        lines.append(
            "- Core logic stays inside core/"
        )

        lines.append(
            "- Agent logic stays inside agents/"
        )

        lines.append("")

        lines.append("## Project Context")

        lines.append("")

        lines.append(
            f"- current_state.md: "
            f"{'FOUND' if current_state else 'MISSING'}"
        )

        lines.append(
            f"- dependency_map.md: "
            f"{'FOUND' if dependency_map else 'MISSING'}"
        )

        lines.append(
            f"- pipeline_map.md: "
            f"{'FOUND' if pipeline_map else 'MISSING'}"
        )

        lines.append(
            f"- file_ownership.md: "
            f"{'FOUND' if file_ownership else 'MISSING'}"
        )

        lines.append(
            f"- impact_report.md: "
            f"{'FOUND' if impact_report else 'MISSING'}"
        )

        lines.append("")

        lines.append("## Suggested Workflow")

        workflow_steps = [
            "Understand requested change",
            "Identify affected files",
            "Check dependency map",
            "Check impact report",
            "Create backup before edits",
            "Apply minimal code change",
            "Run project scanner",
            "Update project brain",
            "Generate new CHAT_HANDOFF.md",
        ]

        for index, step in enumerate(
            workflow_steps,
            start=1
        ):
            lines.append(f"{index}. {step}")

        lines.append("")

        lines.append("## Next Recommended Action")

        lines.append(
            "Connect CoderAgent to main.py "
            "as a safe planning-only tool."
        )

        return "\n".join(lines)

    def write_plan(self, user_goal: str) -> str:
        plan = self.analyze_request(user_goal)

        output_path = (
            self.brain_dir / "coder_plan.md"
        )

        output_path.write_text(
            plan,
            encoding="utf-8"
        )

        change_log = (
            self.brain_dir / "change_log.md"
        )

        with change_log.open(
            "a",
            encoding="utf-8"
        ) as file:

            file.write("\n")
            file.write("\n")
            file.write(
                "## Coder Agent Plan Generated\n"
            )

            file.write(
                f"- Time: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )

            file.write(
                f"- Goal: {user_goal}\n"
            )

            file.write(
                "- Output: "
                "project_brain/coder_plan.md\n"
            )

        return str(output_path)

    def run(self, user_goal: str) -> None:
        print("")
        print("=" * 60)
        print("MODIRAGENT CODER AGENT")
        print("=" * 60)

        print("")
        print(f"Goal: {user_goal}")

        output = self.write_plan(user_goal)

        print("")
        print(f"Plan saved to: {output}")
        print("")


if __name__ == "__main__":
    agent = CoderAgent(".")

    agent.run(
        "Create safe coding workflow"
    )