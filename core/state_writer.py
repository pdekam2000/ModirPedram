from pathlib import Path
from datetime import datetime


BRAIN_FILES = {
    "roadmap.md": "# ROADMAP\n\n",
    "decisions.md": "# DECISIONS\n\n",
    "known_issues.md": "# KNOWN ISSUES\n\n",
    "pipeline_map.md": "# PIPELINE MAP\n\n",
    "file_ownership.md": "# FILE OWNERSHIP\n\n",
    "change_log.md": "# CHANGE LOG\n\n",
    "next_steps.md": "# NEXT STEPS\n\n",
}


def ensure_project_brain(project_root: str = ".") -> None:
    root = Path(project_root).resolve()
    brain_path = root / "project_brain"

    brain_path.mkdir(parents=True, exist_ok=True)

    for filename, starter_content in BRAIN_FILES.items():
        file_path = brain_path / filename

        if not file_path.exists():
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            content = (
                starter_content
                + f"Created automatically by ModirAgent OS\n"
                + f"Created at: {timestamp}\n"
            )

            file_path.write_text(content, encoding="utf-8")


def append_change_log(message: str, project_root: str = ".") -> None:
    root = Path(project_root).resolve()
    log_file = root / "project_brain" / "change_log.md"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = (
        f"\n"
        f"## {timestamp}\n"
        f"- {message}\n"
    )

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)


if __name__ == "__main__":
    ensure_project_brain(".")
    append_change_log("Initialized project brain structure.")

    print("Project brain initialized successfully.")