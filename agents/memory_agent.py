from pathlib import Path
from datetime import datetime


BRAIN_FILES = [
    "current_state.md",
    "roadmap.md",
    "decisions.md",
    "next_steps.md",
    "known_issues.md",
    "pipeline_map.md",
]


class MemoryAgent:
    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()
        self.brain_path = self.root / "project_brain"

    def read_brain_files(self) -> dict:
        memory_data = {}

        for file_name in BRAIN_FILES:
            file_path = self.brain_path / file_name

            if file_path.exists():
                try:
                    content = file_path.read_text(
                        encoding="utf-8"
                    )

                    memory_data[file_name] = content

                except Exception as e:
                    memory_data[file_name] = (
                        f"[ERROR READING FILE: {e}]"
                    )

        return memory_data

    def build_memory_summary(self) -> str:
        memory_data = self.read_brain_files()

        lines = []

        lines.append("# MEMORY SUMMARY")
        lines.append("")

        lines.append(
            f"Generated at: "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        lines.append("")

        for file_name, content in memory_data.items():
            lines.append(f"## {file_name}")
            lines.append("")

            short_content = content[:1000]

            lines.append(short_content)
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def save_memory_snapshot(self) -> str:
        summary = self.build_memory_summary()

        output_file = (
            self.brain_path / "memory_snapshot.md"
        )

        output_file.write_text(
            summary,
            encoding="utf-8"
        )

        return str(output_file)

    def run(self) -> None:
        print("")
        print("=" * 60)
        print("MODIRAGENT MEMORY AGENT")
        print("=" * 60)

        output = self.save_memory_snapshot()

        print("")
        print(f"Memory snapshot saved to: {output}")
        print("")


if __name__ == "__main__":
    agent = MemoryAgent(".")
    agent.run()