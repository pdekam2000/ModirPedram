from pathlib import Path
from datetime import datetime


def file_exists(root: Path, relative_path: str) -> bool:
    return (root / relative_path).exists()


def folder_has_python_files(folder_path: Path) -> bool:
    if not folder_path.exists():
        return False

    return any(file.suffix == ".py" for file in folder_path.glob("*.py"))


def detect_project_stage(project_root: str = ".") -> str:
    root = Path(project_root).resolve()

    core_ready = all([
        file_exists(root, "core/project_scanner.py"),
        file_exists(root, "core/project_reader.py"),
        file_exists(root, "core/state_writer.py"),
        file_exists(root, "core/task_router.py"),
        file_exists(root, "core/safety_guard.py"),
    ])

    if not core_ready:
        return "BOOTSTRAP"

    agents_ready = folder_has_python_files(root / "agents")
    providers_ready = folder_has_python_files(root / "providers")
    execution_ready = folder_has_python_files(root / "execution")

    if core_ready and not agents_ready:
        return "V1_FOUNDATION_READY"

    if agents_ready and not providers_ready:
        return "AGENT_SETUP"

    if agents_ready and providers_ready and not execution_ready:
        return "PROVIDER_SETUP"

    has_orchestrator = file_exists(root, "core/orchestrator.py")

    if agents_ready and providers_ready and execution_ready and not has_orchestrator:
        return "FOUNDATION_STABLE"

    if agents_ready and providers_ready and execution_ready and has_orchestrator:
        return "ORCHESTRATION_READY"

    return "UNKNOWN"


def analyze_missing_components(root: Path) -> list:
    suggestions = []

    checks = [
        (
            "core/safety_guard.py",
            "Create safety_guard.py before allowing automated edits."
        ),
        (
            "project_brain/file_ownership.md",
            "Create file ownership rules for future agents."
        ),
        
        
        
        
    ]

    for relative_path, message in checks:
        if not file_exists(root, relative_path):
            suggestions.append(message)

    return suggestions


def suggest_next_steps(project_root: str = ".") -> list:
    root = Path(project_root).resolve()

    dynamic_suggestions = analyze_missing_components(root)

    if dynamic_suggestions:
        return dynamic_suggestions

    return [
        "Project foundation looks stable.",
        "Next step: begin intelligent agent orchestration.",
    ]


def write_next_steps(project_root: str = ".") -> None:
    root = Path(project_root).resolve()
    output_file = root / "project_brain" / "next_steps.md"

    stage = detect_project_stage(project_root)
    suggestions = suggest_next_steps(project_root)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("# NEXT STEPS")
    lines.append("")
    lines.append(f"Updated at: {timestamp}")
    lines.append(f"Detected stage: `{stage}`")
    lines.append("")
    lines.append("## Suggested Next Steps")
    lines.append("")

    for index, suggestion in enumerate(suggestions, start=1):
        lines.append(f"{index}. {suggestion}")

    lines.append("")

    output_file.write_text("\n".join(lines), encoding="utf-8")


def print_project_analysis(project_root: str = ".") -> None:
    stage = detect_project_stage(project_root)
    suggestions = suggest_next_steps(project_root)

    print("")
    print("=" * 60)
    print("MODIRAGENT PROJECT ANALYSIS")
    print("=" * 60)

    print(f"\nDetected Stage: {stage}\n")

    print("Suggested Next Steps:\n")

    for index, item in enumerate(suggestions, start=1):
        print(f"{index}. {item}")

    write_next_steps(project_root)

    print("")
    print("Saved to: project_brain/next_steps.md")
    print("")


if __name__ == "__main__":
    print_project_analysis(".")