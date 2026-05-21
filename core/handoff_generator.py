from pathlib import Path
from datetime import datetime


IMPORTANT_FILES = [
    "project_brain/current_state.md",
    "project_brain/roadmap.md",
    "project_brain/decisions.md",
    "project_brain/next_steps.md",
    "project_brain/known_issues.md",
    "project_brain/pipeline_map.md",
    "project_brain/dependency_map.md",
    "project_brain/impact_report.md",
]

def read_file_safe(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"[ERROR READING FILE: {e}]"


def generate_handoff(project_root: str = ".") -> str:
    root = Path(project_root).resolve()

    lines = []

    lines.append("# MODIRAGENT OS - CHAT HANDOFF")
    lines.append("")
    lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append("## PROJECT STATUS")
    lines.append("")

    summary_checks = {
        "Scanner": "core/project_scanner.py",
        "Reader": "core/project_reader.py",
        "Task Router": "core/task_router.py",
        "Safety Guard": "core/safety_guard.py",
        "Command Runner": "execution/command_runner.py",
        "Rollback Manager": "execution/rollback_manager.py",
        "OpenAI Provider": "providers/openai_provider.py",
        "Architect Agent": "agents/architect_agent.py",
    }

    for label, relative_path in summary_checks.items():
        exists = (root / relative_path).exists()
        status = "READY" if exists else "MISSING"
        lines.append(f"- {label}: {status}")

    lines.append("")
    lines.append("## IMPORTANT PROJECT FILES")
    lines.append("")

    for relative_path in IMPORTANT_FILES:
        file_path = root / relative_path

        lines.append(f"### {relative_path}")
        lines.append("")

        if file_path.exists():
            content = read_file_safe(file_path)
            lines.append(content[:3000])
        else:
            lines.append("[FILE NOT FOUND]")

        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## CURRENT GOAL")
    lines.append("")
    lines.append(
        "Continue evolving ModirAgent OS into a state-aware "
        "AI project orchestration system."
    )

    return "\n".join(lines)


def save_handoff(project_root: str = ".") -> str:
    root = Path(project_root).resolve()

    output_path = root / "project_brain" / "CHAT_HANDOFF.md"

    content = generate_handoff(project_root)

    output_path.write_text(content, encoding="utf-8")

    return str(output_path)


if __name__ == "__main__":
    output = save_handoff(".")
    print(f"Handoff generated: {output}")