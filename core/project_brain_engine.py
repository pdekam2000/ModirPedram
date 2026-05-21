import ast
import os
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(".")

BRAIN_DIR = PROJECT_ROOT / "project_brain"

IGNORE_DIRS = {
    "venv",
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "outputs",
    "downloads",
    "node_modules",
    "dist",
    "build",
    "backup_temp",
}

MAIN_REPORT = BRAIN_DIR / "SYSTEM_MAP.md"
PIPELINE_REPORT = BRAIN_DIR / "ACTIVE_PIPELINE.md"
FLOW_REPORT = BRAIN_DIR / "EXECUTION_FLOW.md"
DEAD_REPORT = BRAIN_DIR / "DEAD_FILES_REPORT.md"


def should_ignore(path: Path):

    for part in path.parts:
        if part in IGNORE_DIRS:
            return True

    return False


def get_python_files():

    files = []

    for root, dirs, filenames in os.walk(PROJECT_ROOT):

        dirs[:] = [
            d for d in dirs
            if d not in IGNORE_DIRS
        ]

        for filename in filenames:

            if not filename.endswith(".py"):
                continue

            full_path = Path(root) / filename

            if should_ignore(full_path):
                continue

            files.append(full_path)

    return files


def extract_imports(file_path: Path):

    imports = []

    try:

        content = file_path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        tree = ast.parse(content)

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):

                for name in node.names:
                    imports.append(name.name)

            elif isinstance(node, ast.ImportFrom):

                if node.module:
                    imports.append(node.module)

    except:
        pass

    return sorted(set(imports))


def detect_file_role(file_path: Path):

    name = file_path.name.lower()

    if name == "main.py":
        return "MAIN_ENTRY"

    if "orchestrator" in name:
        return "ORCHESTRATOR"

    if "provider" in name:
        return "PROVIDER"

    if "engine" in name:
        return "ENGINE"

    if "agent" in name:
        return "AGENT"

    if "test_" in name:
        return "TEST"

    if "scanner" in name:
        return "SCANNER"

    if "config" in name:
        return "CONFIG"

    if "ui" in str(file_path).lower():
        return "UI"

    return "GENERAL"


def detect_pipeline_priority(file_path: Path):

    name = file_path.name.lower()

    if name == "full_selfcare_factory.py":
        return 100

    if name == "test_full_ai_video_pipeline.py":
        return 95

    if name == "main.py":
        return 90

    if "orchestrator" in name:
        return 85

    if "engine" in name:
        return 70

    if "provider" in name:
        return 60

    if "agent" in name:
        return 50

    if "test_" in name:
        return 20

    return 10


def analyze_project():

    analysis = []

    python_files = get_python_files()

    for file_path in python_files:

        try:
            size_kb = round(
                file_path.stat().st_size / 1024,
                2
            )
        except:
            size_kb = 0

        imports = extract_imports(file_path)

        role = detect_file_role(file_path)

        priority = detect_pipeline_priority(file_path)

        analysis.append({
            "path": str(file_path),
            "role": role,
            "priority": priority,
            "imports": imports,
            "size_kb": size_kb,
        })

    return analysis


def build_system_map(analysis):

    lines = []

    lines.append("# SYSTEM MAP")
    lines.append("")

    lines.append(
        f"Generated: {datetime.now()}"
    )

    lines.append("")

    roles = {}

    for item in analysis:

        role = item["role"]

        if role not in roles:
            roles[role] = []

        roles[role].append(item)

    for role, items in sorted(roles.items()):

        lines.append(f"## {role}")
        lines.append("")

        for item in sorted(
            items,
            key=lambda x: x["priority"],
            reverse=True
        ):

            lines.append(
                f"- {item['path']} "
                f"(priority={item['priority']})"
            )

        lines.append("")

    return "\n".join(lines)


def build_active_pipeline(analysis):

    lines = []

    lines.append("# ACTIVE PIPELINE")
    lines.append("")

    sorted_items = sorted(
        analysis,
        key=lambda x: x["priority"],
        reverse=True
    )

    active = sorted_items[:20]

    lines.append(
        "Top priority execution files:"
    )

    lines.append("")

    for item in active:

        lines.append(
            f"- {item['path']} "
            f"| role={item['role']} "
            f"| priority={item['priority']}"
        )

    lines.append("")

    lines.append("Likely active pipeline:")
    lines.append("")

    lines.append(
        "Trend Discovery -> "
        "Content Engine -> "
        "Timeline Engine -> "
        "Voice Provider -> "
        "Hailuo Video -> "
        "Clip Sync -> "
        "Subtitle Engine -> "
        "Music Engine -> "
        "Overlay Engines -> "
        "SEO -> "
        "Publishing -> "
        "AI Learning"
    )

    return "\n".join(lines)


def build_execution_flow(analysis):

    lines = []

    lines.append("# EXECUTION FLOW")
    lines.append("")

    important = sorted(
        analysis,
        key=lambda x: x["priority"],
        reverse=True
    )[:25]

    for item in important:

        lines.append("---")
        lines.append("")

        lines.append(
            f"FILE: {item['path']}"
        )

        lines.append(
            f"ROLE: {item['role']}"
        )

        lines.append(
            f"PRIORITY: {item['priority']}"
        )

        lines.append("")

        if item["imports"]:

            lines.append("IMPORTS:")

            for imp in item["imports"][:20]:

                lines.append(f" - {imp}")

        lines.append("")

    return "\n".join(lines)


def build_dead_file_report(analysis):

    lines = []

    lines.append("# POSSIBLE TEST / LOW PRIORITY FILES")
    lines.append("")

    low_priority = [
        x for x in analysis
        if x["priority"] <= 20
    ]

    for item in low_priority:

        lines.append(
            f"- {item['path']}"
        )

    return "\n".join(lines)


def save_report(path: Path, content: str):

    BRAIN_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        content,
        encoding="utf-8"
    )


def main():

    print("\n" + "=" * 80)
    print("PROJECT BRAIN ENGINE")
    print("=" * 80)

    print("\n[1] Analyzing project...")
    analysis = analyze_project()

    print(
        f"[OK] Python files analyzed: "
        f"{len(analysis)}"
    )

    print("\n[2] Building reports...")

    system_map = build_system_map(
        analysis
    )

    active_pipeline = build_active_pipeline(
        analysis
    )

    execution_flow = build_execution_flow(
        analysis
    )

    dead_report = build_dead_file_report(
        analysis
    )

    print("\n[3] Saving reports...")

    save_report(
        MAIN_REPORT,
        system_map
    )

    save_report(
        PIPELINE_REPORT,
        active_pipeline
    )

    save_report(
        FLOW_REPORT,
        execution_flow
    )

    save_report(
        DEAD_REPORT,
        dead_report
    )

    print("\n" + "=" * 80)
    print("PROJECT BRAIN COMPLETE")
    print("=" * 80)

    print("\nGenerated files:")
    print("-", MAIN_REPORT)
    print("-", PIPELINE_REPORT)
    print("-", FLOW_REPORT)
    print("-", DEAD_REPORT)


if __name__ == "__main__":
    main()