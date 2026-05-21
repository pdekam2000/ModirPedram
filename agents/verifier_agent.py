from datetime import datetime
from pathlib import Path


REQUIRED_BRAIN_FILES = [
    "current_state.md",
    "roadmap.md",
    "decisions.md",
    "known_issues.md",
    "pipeline_map.md",
    "file_ownership.md",
    "change_log.md",
    "next_steps.md",
    "CHAT_HANDOFF.md",
]


class VerifierAgent:
    """
    Verification & Consistency Agent

    Purpose:
    - Verify project structure
    - Detect missing brain files
    - Detect missing core modules
    - Detect architecture inconsistencies
    - Generate verification report
    """

    def __init__(self, project_root="."):
        self.project_root = Path(
            project_root
        ).resolve()

        self.brain_dir = (
            self.project_root / "project_brain"
        )

    def verify_brain_files(self) -> list:
        results = []

        for file_name in REQUIRED_BRAIN_FILES:
            path = self.brain_dir / file_name

            if path.exists():
                results.append(
                    f"[OK] {file_name}"
                )
            else:
                results.append(
                    f"[MISSING] {file_name}"
                )

        return results

    def verify_core_modules(self) -> list:
        required_modules = [
            "core/project_scanner.py",
            "core/project_reader.py",
            "core/task_router.py",
            "core/orchestrator.py",
            "core/dependency_mapper.py",
            "core/impact_analyzer.py",
        ]

        results = []

        for module in required_modules:
            path = self.project_root / module

            if path.exists():
                results.append(
                    f"[OK] {module}"
                )
            else:
                results.append(
                    f"[MISSING] {module}"
                )

        return results

    def build_report(self) -> str:
        lines = []

        lines.append(
            "# VERIFIER AGENT REPORT"
        )

        lines.append("")

        lines.append(
            f"Generated at: "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        lines.append("")

        lines.append(
            "## Brain File Verification"
        )

        lines.append("")

        for result in self.verify_brain_files():
            lines.append(result)

        lines.append("")
        lines.append(
            "## Core Module Verification"
        )

        lines.append("")

        for result in self.verify_core_modules():
            lines.append(result)

        lines.append("")
        lines.append(
            "## Verification Summary"
        )

        lines.append("")
        lines.append(
            "- Verification completed"
        )

        lines.append(
            "- No automatic fixing performed"
        )

        lines.append(
            "- System remains in safe mode"
        )

        return "\n".join(lines)

    def save_report(self) -> str:
        report = self.build_report()

        output_path = (
            self.brain_dir
            / "verification_report.md"
        )

        output_path.write_text(
            report,
            encoding="utf-8"
        )

        return str(output_path)

    def run(self):
        print("")
        print("=" * 60)
        print("MODIRAGENT VERIFIER AGENT")
        print("=" * 60)

        output = self.save_report()

        print("")
        print(f"Verification saved to: {output}")
        print("")


if __name__ == "__main__":
    agent = VerifierAgent(".")
    agent.run()