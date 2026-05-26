from pathlib import Path
from datetime import datetime
import re


IMPORT_PATTERN = re.compile(
    r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))",
    re.MULTILINE
)


IGNORE_DIRS = {
    "venv",
    ".venv",
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
    "backup",
    "backups",
    "ModirAgentOS_CORE_BACKUPaussssssss",
    "ModirAgentOS_CORE_BACKUP",

    "storage",
    "browser_session",
    "real_chrome_profile",

    "Default",
    "Cache",
    "Code Cache",
    "GPUCache",
    "IndexedDB",
    "Local Storage",
    "Session Storage",
    "Service Worker",
    "Crashpad",
    "ShaderCache",
    "GrShaderCache",
    "GraphiteDawnCache",
}


class DependencyMapper:
    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()

    def should_ignore(self, path: Path) -> bool:
        return any(
            part in IGNORE_DIRS
            for part in path.parts
        )

    def get_python_files(self) -> list:
        return [
            file for file in self.root.rglob("*.py")
            if not self.should_ignore(file)
        ]

    def extract_imports(self, file_path: Path) -> list:
        try:
            content = file_path.read_text(
                encoding="utf-8",
                errors="ignore"
            )
        except Exception:
            return []

        imports = []

        matches = IMPORT_PATTERN.findall(content)

        for match in matches:
            import_name = match[0] or match[1]

            if import_name:
                imports.append(import_name)

        return sorted(set(imports))

    def build_dependency_map(self) -> dict:
        dependency_map = {}

        python_files = self.get_python_files()

        for file_path in python_files:
            relative_path = file_path.relative_to(self.root)

            dependency_map[str(relative_path)] = {
                "imports": self.extract_imports(file_path)
            }

        return dependency_map

    def save_dependency_map(self, dependency_map: dict) -> str:
        output_file = self.root / "project_brain" / "dependency_map.md"

        lines = []

        lines.append("# DEPENDENCY MAP")
        lines.append("")
        lines.append(
            f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append("")

        for file_name, data in dependency_map.items():
            normalized = file_name.replace("\\", "/")

            if any(
                part in IGNORE_DIRS
                for part in normalized.split("/")
            ):
                continue

            lines.append(f"## {file_name}")
            lines.append("")

            imports = data["imports"]

            if imports:
                for item in imports:
                    lines.append(f"- {item}")
            else:
                lines.append("- No imports detected")

            lines.append("")

        output_file.write_text(
            "\n".join(lines),
            encoding="utf-8"
        )

        return str(output_file)

    def run(self) -> None:
        print("")
        print("=" * 60)
        print("MODIRAGENT DEPENDENCY MAPPER")
        print("=" * 60)

        dependency_map = self.build_dependency_map()

        output = self.save_dependency_map(dependency_map)

        print("")
        print(f"Mapped {len(dependency_map)} Python files.")
        print(f"Saved to: {output}")
        print("")


if __name__ == "__main__":
    mapper = DependencyMapper(".")
    mapper.run()