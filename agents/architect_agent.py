from pathlib import Path
from datetime import datetime


class ArchitectAgent:
    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()
        self.brain_path = self.root / "project_brain"

    def analyze_architecture(self) -> dict:
        main_file = self.root / "main.py"
        core_path = self.root / "core"
        agents_path = self.root / "agents"
        providers_path = self.root / "providers"
        execution_path = self.root / "execution"

        return {
            "main_exists": main_file.exists(),
            "core_exists": core_path.exists(),
            "agents_exists": agents_path.exists(),
            "providers_exists": providers_path.exists(),
            "execution_exists": execution_path.exists(),
            "main_size_bytes": main_file.stat().st_size if main_file.exists() else 0,
        }

    def write_architecture_note(self) -> None:
        analysis = self.analyze_architecture()
        output_file = self.brain_path / "decisions.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = []
        lines.append("\n")
        lines.append(f"## Architecture Review - {timestamp}")
        lines.append("")
        lines.append(f"- main.py exists: {analysis['main_exists']}")
        lines.append(f"- core folder exists: {analysis['core_exists']}")
        lines.append(f"- agents folder exists: {analysis['agents_exists']}")
        lines.append(f"- providers folder exists: {analysis['providers_exists']}")
        lines.append(f"- execution folder exists: {analysis['execution_exists']}")
        lines.append(f"- main.py size: {analysis['main_size_bytes']} bytes")
        lines.append("")
        lines.append("Decision:")
        lines.append("- Keep main.py minimal.")
        lines.append("- Keep core logic inside core modules.")
        lines.append("- Keep providers isolated from project logic.")
        lines.append("- Keep execution tools isolated from planning logic.")
        lines.append("")

        with open(output_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def run(self) -> None:
        self.write_architecture_note()
        print("ArchitectAgent completed architecture review.")
        print("Saved to: project_brain/decisions.md")


if __name__ == "__main__":
    agent = ArchitectAgent(".")
    agent.run()

    