from pathlib import Path
from datetime import datetime

from core.project_reader import load_project_brain


class Orchestrator:
    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()
        self.brain = load_project_brain(project_root)

    def analyze_goal(self, goal: str) -> dict:
        goal_lower = goal.lower()

        analysis = {
            "goal": goal,
            "needs_architect": False,
            "needs_execution": False,
            "needs_provider": False,
            "needs_memory": False,
            "needs_dependency_analysis": False,
            "needs_impact_analysis": False,
            "needs_safety": False,
            "needs_planning": True,
        }

        architecture_keywords = [
            "architecture",
            "structure",
            "design",
            "refactor",
        ]

        execution_keywords = [
            "execution",
            "command",
            "run",
            "execute",
        ]

        provider_keywords = [
            "provider",
            "openai",
            "anthropic",
            "gemini",
        ]

        memory_keywords = [
            "memory",
            "brain",
            "context",
            "handoff",
        ]

        dependency_keywords = [
            "dependency",
            "import",
            "relationship",
        ]

        impact_keywords = [
            "impact",
            "break",
            "affected",
        ]

        safety_keywords = [
            "safety",
            "secure",
            "protection",
            "guard",
        ]

        if any(word in goal_lower for word in architecture_keywords):
            analysis["needs_architect"] = True

        if any(word in goal_lower for word in execution_keywords):
            analysis["needs_execution"] = True

        if any(word in goal_lower for word in provider_keywords):
            analysis["needs_provider"] = True

        if any(word in goal_lower for word in memory_keywords):
            analysis["needs_memory"] = True

        if any(word in goal_lower for word in dependency_keywords):
            analysis["needs_dependency_analysis"] = True

        if any(word in goal_lower for word in impact_keywords):
            analysis["needs_impact_analysis"] = True

        if any(word in goal_lower for word in safety_keywords):
            analysis["needs_safety"] = True

        return analysis

    def build_execution_plan(self, goal: str) -> list:
        analysis = self.analyze_goal(goal)

        plan = []

        plan.append("Read Project Brain")

        if analysis["needs_architect"]:
            plan.append("Run ArchitectAgent")

        if analysis["needs_safety"]:
            plan.append("Validate SafetyGuard")

        if analysis["needs_execution"]:
            plan.append("Use CommandRunner")

        if analysis["needs_provider"]:
            plan.append("Check Provider Layer")

        if analysis["needs_memory"]:
            plan.append("Run MemoryAgent")

        if analysis["needs_dependency_analysis"]:
            plan.append("Run DependencyMapper")

        if analysis["needs_impact_analysis"]:
            plan.append("Run ImpactAnalyzer")

        if analysis["needs_planning"]:
            plan.append("Update Project Brain")

        return plan

    def save_execution_plan(self, goal: str, plan: list) -> str:
        output_file = self.root / "project_brain" / "next_steps.md"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = []

        lines.append("# ORCHESTRATION PLAN")
        lines.append("")

        lines.append(
            f"Generated at: {timestamp}"
        )

        lines.append(f"Goal: {goal}")

        lines.append("")
        lines.append("## Execution Plan")
        lines.append("")

        for index, step in enumerate(plan, start=1):
            lines.append(f"{index}. {step}")

        lines.append("")

        output_file.write_text(
            "\n".join(lines),
            encoding="utf-8"
        )

        return str(output_file)

    def run(self, goal: str) -> None:
        print("")
        print("=" * 60)
        print("MODIRAGENT ORCHESTRATOR")
        print("=" * 60)

        print(f"\nGoal: {goal}\n")

        plan = self.build_execution_plan(goal)

        print("Execution Plan:\n")

        for index, step in enumerate(plan, start=1):
            print(f"{index}. {step}")

        output = self.save_execution_plan(goal, plan)

        print("")
        print(f"Saved plan to: {output}")
        print("")


if __name__ == "__main__":
    orchestrator = Orchestrator(".")

    orchestrator.run(
        "Improve architecture safety and execution planning"
    )
    