from pathlib import Path
from datetime import datetime

from core.dependency_mapper import DependencyMapper


class ImpactAnalyzer:
    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()

        mapper = DependencyMapper(project_root)
        self.dependency_map = mapper.build_dependency_map()

    def normalize_module_name(self, file_path: str) -> str:
        return (
            file_path
            .replace("\\", ".")
            .replace("/", ".")
            .replace(".py", "")
        )

    def analyze_impact(self, changed_file: str) -> dict:
        normalized_target = self.normalize_module_name(changed_file)

        impacted_files = []

        for file_name, data in self.dependency_map.items():
            imports = data["imports"]

            for imported_module in imports:
                if imported_module == normalized_target:
                    impacted_files.append(file_name)

        return {
            "changed_file": changed_file,
            "normalized_module": normalized_target,
            "impacted_files": sorted(set(impacted_files)),
        }

    def save_report(self, result: dict) -> str:
        output_file = self.root / "project_brain" / "impact_report.md"

        lines = []

        lines.append("# IMPACT ANALYSIS REPORT")
        lines.append("")
        lines.append(
            f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append("")

        lines.append(f"Changed file: `{result['changed_file']}`")
        lines.append(
            f"Normalized module: `{result['normalized_module']}`"
        )
        lines.append("")

        lines.append("## Potentially Impacted Files")
        lines.append("")

        if result["impacted_files"]:
            for item in result["impacted_files"]:
                lines.append(f"- {item}")
        else:
            lines.append("- No impacted files detected")

        lines.append("")

        output_file.write_text(
            "\n".join(lines),
            encoding="utf-8"
        )

        return str(output_file)

    def run(self, changed_file: str) -> None:
        print("")
        print("=" * 60)
        print("MODIRAGENT IMPACT ANALYZER")
        print("=" * 60)

        result = self.analyze_impact(changed_file)

        print("")
        print(f"Changed file: {changed_file}")
        print("")

        if result["impacted_files"]:
            print("Potentially impacted files:\n")

            for item in result["impacted_files"]:
                print(f"- {item}")
        else:
            print("No impacted files detected.")

        output = self.save_report(result)

        print("")
        print(f"Saved to: {output}")
        print("")


if __name__ == "__main__":
    analyzer = ImpactAnalyzer(".")

    analyzer.run("core/task_router.py")