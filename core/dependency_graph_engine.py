from pathlib import Path
from datetime import datetime
import re
import sys


IMPORT_PATTERN = re.compile(
    r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))",
    re.MULTILINE
)


class DependencyGraphEngine:
    """
    Dependency Graph Engine V1

    Purpose:
    - Scan Python files
    - Build direct dependency graph
    - Build reverse dependency graph
    - Find impact chain for a target file/module
    - Save report to project_brain/dependency_graph_report.md

    Safe mode:
    - Does NOT edit files
    - Analysis only
    """

    def __init__(self, project_root="."):
        self.project_root = Path(project_root).resolve()
        self.brain_dir = self.project_root / "project_brain"
        self.output_file = self.brain_dir / "dependency_graph_report.md"

        self.skip_dirs = {
            "venv",
            ".venv",
            "__pycache__",
            ".git",
            "outputs",
            "downloads",
            "backups",
            "backup_temp",
            "storage",
            "browser_session",
            "real_chrome_profile",
            "ModirAgentOS_CORE_BACKUPaussssssss",
        }

    def should_skip_path(self, path: Path) -> bool:
        parts = set(path.parts)

        for skip_dir in self.skip_dirs:
            if skip_dir in parts:
                return True

        return False

    def get_python_files(self) -> list:
        files = []

        for file in self.project_root.rglob("*.py"):
            if self.should_skip_path(file):
                continue

            files.append(file)

        return sorted(files)

    def file_to_module(self, file_path: Path) -> str:
        relative = file_path.relative_to(self.project_root)
        parts = list(relative.parts)

        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1].replace(".py", "")

        return ".".join(parts)

    def module_to_file_candidates(self, module_name: str) -> list:
        path = module_name.replace(".", "/")

        return [
            path + ".py",
            path + "/__init__.py",
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

    def build_graphs(self):
        python_files = self.get_python_files()

        module_to_file = {}
        file_to_module = {}

        # --------------------------------------
        # BUILD MODULE MAP
        # --------------------------------------

        for file in python_files:
            relative = str(
                file.relative_to(self.project_root)
            ).replace("\\", "/")

            module = self.file_to_module(file)

            module_to_file[module] = relative
            file_to_module[relative] = module

        direct_graph = {}
        reverse_graph = {}

        # --------------------------------------
        # INIT
        # --------------------------------------

        for file in file_to_module:
            direct_graph[file] = []
            reverse_graph[file] = []

        # --------------------------------------
        # BUILD RELATIONSHIPS
        # --------------------------------------

        for file in python_files:
            relative = str(
                file.relative_to(self.project_root)
            ).replace("\\", "/")

            imports = self.extract_imports(file)

            for imported_module in imports:
                matched_files = []

                for module_name, module_file in module_to_file.items():
                    if (
                        imported_module == module_name
                        or imported_module.startswith(module_name + ".")
                        or module_name.startswith(imported_module + ".")
                    ):
                        matched_files.append(module_file)

                for matched_file in matched_files:
                    if matched_file == relative:
                        continue

                    if matched_file not in direct_graph[relative]:
                        direct_graph[relative].append(matched_file)

                    if relative not in reverse_graph[matched_file]:
                        reverse_graph[matched_file].append(relative)

        # --------------------------------------
        # SORT
        # --------------------------------------

        for file in direct_graph:
            direct_graph[file] = sorted(set(direct_graph[file]))

        for file in reverse_graph:
            reverse_graph[file] = sorted(set(reverse_graph[file]))

        return (
            direct_graph,
            reverse_graph,
            file_to_module,
            module_to_file,
        )

    def normalize_target(self, target: str, module_to_file: dict) -> str:
        target = target.strip().replace("\\", "/")

        if not target:
            return ""

        if target.endswith(".py"):
            return target

        if target in module_to_file:
            return module_to_file[target]

        for module, file in module_to_file.items():
            if target == module:
                return file

            if target in module:
                return file

            if target.replace("/", ".") == module:
                return file

        possible = target.replace(".", "/") + ".py"

        if (self.project_root / possible).exists():
            return possible

        return target

    def walk_reverse_dependencies(
        self,
        target_file: str,
        reverse_graph: dict,
        max_depth: int = 3
    ) -> dict:
        levels = {}
        visited = {target_file}
        current_level = [target_file]

        for depth in range(1, max_depth + 1):
            next_level = []

            for file in current_level:
                dependents = reverse_graph.get(file, [])

                for dependent in dependents:
                    if dependent in visited:
                        continue

                    visited.add(dependent)
                    next_level.append(dependent)

            levels[depth] = sorted(set(next_level))
            current_level = next_level

            if not current_level:
                break

        return levels

    def walk_direct_dependencies(
        self,
        target_file: str,
        direct_graph: dict,
        max_depth: int = 2
    ) -> dict:
        levels = {}
        visited = {target_file}
        current_level = [target_file]

        for depth in range(1, max_depth + 1):
            next_level = []

            for file in current_level:
                dependencies = direct_graph.get(file, [])

                for dependency in dependencies:
                    if dependency in visited:
                        continue

                    visited.add(dependency)
                    next_level.append(dependency)

            levels[depth] = sorted(set(next_level))
            current_level = next_level

            if not current_level:
                break

        return levels

    def estimate_risk(
        self,
        target_file: str,
        reverse_levels: dict,
        direct_levels: dict
    ) -> str:
        risk_points = 0
        all_files = [target_file]

        for files in reverse_levels.values():
            all_files.extend(files)

        for files in direct_levels.values():
            all_files.extend(files)

        all_files = sorted(set(all_files))

        for file in all_files:
            lower = file.lower()

            if lower in ["main.py", "ui/app.py"]:
                risk_points += 5

            if "pipeline" in lower:
                risk_points += 4

            if "orchestrator" in lower:
                risk_points += 4

            if "provider" in lower:
                risk_points += 3

            if "router" in lower:
                risk_points += 3

            if "config" in lower:
                risk_points += 2

        if len(all_files) >= 20:
            risk_points += 5
        elif len(all_files) >= 10:
            risk_points += 3
        elif len(all_files) >= 5:
            risk_points += 1

        if risk_points >= 16:
            return "CRITICAL"

        if risk_points >= 10:
            return "HIGH"

        if risk_points >= 5:
            return "MEDIUM"

        return "LOW"

    def generate_report(self, target: str) -> str:
        (
            direct_graph,
            reverse_graph,
            file_to_module,
            module_to_file,
        ) = self.build_graphs()

        target_file = self.normalize_target(
            target,
            module_to_file
        )

        reverse_levels = self.walk_reverse_dependencies(
            target_file=target_file,
            reverse_graph=reverse_graph,
            max_depth=4
        )

        direct_levels = self.walk_direct_dependencies(
            target_file=target_file,
            direct_graph=direct_graph,
            max_depth=3
        )

        risk = self.estimate_risk(
            target_file,
            reverse_levels,
            direct_levels
        )

        lines = []

        lines.append("# DEPENDENCY GRAPH REPORT")
        lines.append("")
        lines.append(
            f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append("")
        lines.append(f"Target input: `{target}`")
        lines.append(f"Resolved target file: `{target_file}`")
        lines.append("")
        lines.append(f"Estimated change risk: **{risk}**")
        lines.append("")

        lines.append("## Direct Dependencies")
        lines.append("")
        lines.append(
            "Files/modules that the target file directly or indirectly uses."
        )
        lines.append("")

        if direct_levels:
            for depth, files in direct_levels.items():
                lines.append(f"### Dependency Level {depth}")
                lines.append("")

                if files:
                    for file in files:
                        lines.append(f"- {file}")
                else:
                    lines.append("- None")

                lines.append("")
        else:
            lines.append("- None")
            lines.append("")

        lines.append("## Reverse Dependencies / Impact Chain")
        lines.append("")
        lines.append(
            "Files that depend on the target file and may be affected by changes."
        )
        lines.append("")

        if reverse_levels:
            for depth, files in reverse_levels.items():
                lines.append(f"### Impact Level {depth}")
                lines.append("")

                if files:
                    for file in files:
                        lines.append(f"- {file}")
                else:
                    lines.append("- None")

                lines.append("")
        else:
            lines.append("- None")
            lines.append("")

        lines.append("## Safe Upgrade Recommendation")
        lines.append("")
        lines.append("1. Review target file first")
        lines.append("2. Review Level 1 impact files")
        lines.append("3. Create backup before edits")
        lines.append("4. Apply minimal change")
        lines.append("5. Run verifier")
        lines.append("6. Run related tests if available")
        lines.append("7. Update project_brain")
        lines.append("")

        lines.append("## Approval Status")
        lines.append("")
        lines.append("WAITING FOR USER APPROVAL")
        lines.append("")
        lines.append("No file was modified by this engine.")

        return "\n".join(lines)

    def save_report(self, report: str) -> str:
        self.brain_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.output_file.write_text(
            report,
            encoding="utf-8"
        )

        change_log = self.brain_dir / "change_log.md"

        with change_log.open(
            "a",
            encoding="utf-8"
        ) as file:
            file.write("\n\n")
            file.write("## Dependency Graph Report Generated\n")
            file.write(
                f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            file.write(
                "- Output: project_brain/dependency_graph_report.md\n"
            )

        return str(self.output_file)

    def run(self, target: str) -> str:
        print("")
        print("=" * 70)
        print("MODIRAGENT DEPENDENCY GRAPH ENGINE")
        print("=" * 70)
        print("")
        print(f"Target: {target}")
        print("")

        report = self.generate_report(target)
        output = self.save_report(report)

        print(f"Dependency graph report saved to: {output}")
        print("")
        print("Mode: ANALYZE ONLY")
        print("No files were modified.")
        print("")

        return output


def main():
    target = "core.video_provider_router"

    if len(sys.argv) >= 2:
        target = sys.argv[1]

    engine = DependencyGraphEngine(".")
    engine.run(target)


if __name__ == "__main__":
    main()