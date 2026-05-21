from pathlib import Path


BRAIN_FILES = [
    "current_state.md",
    "roadmap.md",
    "decisions.md",
    "known_issues.md",
    "pipeline_map.md",
    "file_ownership.md",
    "change_log.md",
    "next_steps.md",
]


def read_file_safe(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"[ERROR READING FILE: {e}]"


def load_project_brain(project_root: str = ".") -> dict:
    root = Path(project_root).resolve()
    brain_path = root / "project_brain"

    data = {}

    for filename in BRAIN_FILES:
        file_path = brain_path / filename

        if file_path.exists():
            data[filename] = read_file_safe(file_path)
        else:
            data[filename] = "[FILE NOT FOUND]"

    return data


def build_project_summary(project_root: str = ".") -> str:
    brain_data = load_project_brain(project_root)

    summary_lines = []

    summary_lines.append("=" * 60)
    summary_lines.append("MODIRAGENT PROJECT SUMMARY")
    summary_lines.append("=" * 60)
    summary_lines.append("")

    for filename, content in brain_data.items():
        summary_lines.append(f"FILE: {filename}")
        summary_lines.append("-" * 60)

        short_content = content[:1200]

        summary_lines.append(short_content)
        summary_lines.append("")
        summary_lines.append("")

    return "\n".join(summary_lines)


if __name__ == "__main__":
    summary = build_project_summary(".")

    print(summary)