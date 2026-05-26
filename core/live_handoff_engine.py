from pathlib import Path
from datetime import datetime


class LiveHandoffEngine:
    """
    Live Handoff Engine V1

    Purpose:
    - Generate fresh CHAT_HANDOFF.md
    - Generate fresh FULL_PROJECT_HANDOFF.md
    - Read latest project_brain reports
    - Prevent stale/old handoff problem
    """

    def __init__(self, project_root="."):
        self.project_root = Path(project_root).resolve()
        self.brain_dir = self.project_root / "project_brain"

        self.chat_handoff = self.brain_dir / "CHAT_HANDOFF.md"
        self.full_handoff = self.brain_dir / "FULL_PROJECT_HANDOFF.md"

    def read_file(self, filename):
        path = self.brain_dir / filename

        if not path.exists():
            return ""

        return path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    def section(self, title, content):
        lines = []
        lines.append("")
        lines.append("=" * 80)
        lines.append(title)
        lines.append("=" * 80)
        lines.append("")

        if content.strip():
            lines.append(content.strip())
        else:
            lines.append("Not available.")

        lines.append("")
        return "\n".join(lines)

    def build_handoff(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        files = {
            "CURRENT STATE": "current_state.md",
            "ACTIVE PIPELINE": "ACTIVE_PIPELINE.md",
            "SYSTEM MAP": "SYSTEM_MAP.md",
            "EXECUTION FLOW": "EXECUTION_FLOW.md",
            "DEPENDENCY GRAPH REPORT": "dependency_graph_report.md",
            "UPGRADE PLAN": "upgrade_plan.md",
            "UPGRADE EXECUTION PLAN": "upgrade_execution_plan.md",
            "PATCH PREVIEW": "patch_preview.md",
            "VERIFICATION REPORT": "verification_report.md",
            "NEXT STEPS": "next_steps.md",
            "CHANGE LOG": "change_log.md",
        }

        lines = []

        lines.append("# MODIRAGENT OS - LIVE PROJECT HANDOFF")
        lines.append("")
        lines.append(f"Generated at: {now}")
        lines.append("")
        lines.append("Status: Fresh handoff generated from current project_brain files.")
        lines.append("")

        lines.append("## Current Milestone")
        lines.append("")
        lines.append("Self Editing Framework V5 completed.")
        lines.append("")
        lines.append("Working modules:")
        lines.append("- ProjectUpgradeAgent")
        lines.append("- DependencyGraphEngine")
        lines.append("- UpgradePlannerEngine")
        lines.append("- ProjectContextAgent")
        lines.append("- ChangeRequestAgent")
        lines.append("- CodeGenerationAgent V2")
        lines.append("- PatchPreviewEngine")
        lines.append("- PatchValidator")
        lines.append("- ApprovalEngine")
        lines.append("- ApplyPatchEngine")
        lines.append("- SafeCodeEditor")
        lines.append("- VerifierAgent")
        lines.append("- SelfEditingAgent V5 CLI")
        lines.append("- LiveHandoffEngine V1")
        lines.append("")

        lines.append("## Verified Capabilities")
        lines.append("")
        lines.append("- CLI goal support")
        lines.append("- Preview mode")
        lines.append("- Approval mode with --approve")
        lines.append("- Backup before apply")
        lines.append("- Patch validation")
        lines.append("- Duplicate function detection")
        lines.append("- Safe append patch")
        lines.append("- Verifier after apply")
        lines.append("- Fresh handoff generation")
        lines.append("")

        lines.append("## Known Current Limitation")
        lines.append("")
        lines.append(
            "Current self-editing supports safe append-style patches. "
            "Modify/replace existing function mode is the next upgrade."
        )
        lines.append("")

        lines.append("## Next Recommended Step")
        lines.append("")
        lines.append(
            "Build Modify Function Mode: detect existing function, generate replacement preview, "
            "validate syntax, require approval, backup, replace exact function block, then verify."
        )
        lines.append("")

        for title, filename in files.items():
            lines.append(
                self.section(
                    title,
                    self.read_file(filename)
                )
            )

        return "\n".join(lines)

    def save(self, content):
        self.brain_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.chat_handoff.write_text(
            content,
            encoding="utf-8"
        )

        self.full_handoff.write_text(
            content,
            encoding="utf-8"
        )

        return str(self.chat_handoff), str(self.full_handoff)

    def run(self):
        print("")
        print("=" * 70)
        print("MODIRAGENT LIVE HANDOFF ENGINE")
        print("=" * 70)

        content = self.build_handoff()
        chat_path, full_path = self.save(content)

        print("")
        print("Fresh handoff generated:")
        print(chat_path)
        print(full_path)
        print("")


if __name__ == "__main__":
    engine = LiveHandoffEngine(".")
    engine.run()