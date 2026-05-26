from pathlib import Path
from datetime import datetime
import sys


class ProjectUpgradeAgent:
    """
    Project Upgrade Agent V2 - Targeted Analyze Mode

    - Scans project safely
    - Ignores backups/cache/output folders
    - Separates Core / Related / Context files
    - Uses keyword relevance + project structure
    - Keeps ANALYZE ONLY mode
    - Does NOT edit files automatically
    """

    def __init__(self, project_root="."):
        self.project_root = Path(project_root).resolve()
        self.brain_dir = self.project_root / "project_brain"
        self.output_file = self.brain_dir / "upgrade_plan.md"

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

        self.allowed_extensions = {
            ".py",
            ".md",
            ".json",
            ".yaml",
            ".yml",
            ".txt",
        }

        self.context_dirs = {
            "project_brain",
        }

        self.core_dirs = {
            "agents",
            "core",
            "engines",
            "providers",
            "orchestrators",
            "pipelines",
            "ui",
            "execution",
            "automation",
            "utils",
            "config",
        }

    # =========================================================
    # BASIC READERS
    # =========================================================

    def read_text_file(self, path: Path) -> str:
        try:
            return path.read_text(
                encoding="utf-8",
                errors="ignore"
            )
        except Exception:
            return ""

    def read_brain_file(self, filename: str) -> str:
        path = self.brain_dir / filename

        if not path.exists():
            return ""

        return self.read_text_file(path)

    # =========================================================
    # SCANNING
    # =========================================================

    def should_skip_path(self, path: Path) -> bool:
        path_parts = set(path.parts)

        for skip_dir in self.skip_dirs:
            if skip_dir in path_parts:
                return True

        return False

    def scan_target(self, target_path: str = "") -> list:
        if target_path:
            target = Path(target_path)

            if not target.is_absolute():
                target = self.project_root / target
        else:
            target = self.project_root

        if not target.exists():
            return []

        files = []

        if target.is_file():
            if target.suffix.lower() in self.allowed_extensions:
                files.append(target)

            return files

        for file in target.rglob("*"):
            if not file.is_file():
                continue

            if self.should_skip_path(file):
                continue

            if file.suffix.lower() not in self.allowed_extensions:
                continue

            files.append(file)

        return sorted(files)

    # =========================================================
    # KEYWORDS
    # =========================================================

    def extract_keywords(self, user_goal: str) -> list:
        raw_words = (
            user_goal
            .replace("_", " ")
            .replace("-", " ")
            .replace("/", " ")
            .replace("\\", " ")
            .split()
        )

        stop_words = {
            "the", "and", "or", "to", "in", "on", "for", "with",
            "a", "an", "this", "that", "be", "is", "are", "can",
            "we", "add", "make", "create", "build", "update",
            "change", "upgrade", "fix", "improve", "analyze",
            "project", "safe", "plan", "system",

            "inja", "ino", "inam", "mikham", "mikhahim",
            "taghir", "ezafe", "beshe", "bokonim", "konim",
            "khodet", "hame", "eslahat", "anjam", "bede",
            "noskhe", "kamel",
        }

        keywords = []

        for word in raw_words:
            clean = "".join(
                char for char in word
                if char.isalnum() or char in ["_", "-"]
            )

            clean = clean.strip().lower()

            if len(clean) < 3:
                continue

            if clean in stop_words:
                continue

            keywords.append(clean)

        return sorted(set(keywords))

    def keyword_score(self, text: str, keywords: list) -> int:
        score = 0
        lower_text = text.lower()

        for keyword in keywords:
            if keyword in lower_text:
                score += 1

        return score

    # =========================================================
    # DEPENDENCY MAP SUPPORT
    # =========================================================

    def parse_dependency_map(self) -> dict:
        dependency_file = self.brain_dir / "dependency_map.md"

        if not dependency_file.exists():
            return {}

        content = self.read_text_file(dependency_file)

        dependency_map = {}
        current_file = None

        for raw_line in content.splitlines():
            line = raw_line.strip()

            if line.startswith("## "):
                current_file = line.replace("## ", "").strip()
                dependency_map[current_file] = []
                continue

            if current_file and line.startswith("- "):
                item = line.replace("- ", "").strip()

                if item and item != "No imports detected":
                    dependency_map[current_file].append(item)

        return dependency_map

    def module_to_possible_paths(self, module_name: str) -> list:
        normalized = module_name.replace(".", "/")

        return [
            normalized + ".py",
            normalized + "/__init__.py",
        ]

    def find_dependency_related_files(
        self,
        affected_files: list,
        dependency_map: dict
    ) -> list:
        affected_names = {
            item["file"].replace("\\", "/")
            for item in affected_files
        }

        related = []

        for file_name, imports in dependency_map.items():
            normalized_file = file_name.replace("\\", "/")

            if normalized_file in affected_names:
                continue

            for imported_module in imports:
                possible_paths = self.module_to_possible_paths(
                    imported_module
                )

                for possible_path in possible_paths:
                    if possible_path in affected_names:
                        related.append(
                            {
                                "file": normalized_file,
                                "score": 1,
                                "path_score": 0,
                                "content_score": 0,
                                "reason": (
                                    "Imports affected module: "
                                    + imported_module
                                ),
                            }
                        )

        unique = {}

        for item in related:
            unique[item["file"]] = item

        return list(unique.values())

    # =========================================================
    # FILE ANALYSIS
    # =========================================================

    def analyze_files(self, files: list, user_goal: str) -> list:
        keywords = self.extract_keywords(user_goal)

        results = []

        for file in files:
            relative_path = file.relative_to(self.project_root)
            relative_str = str(relative_path).replace("\\", "/")

            content = self.read_text_file(file)

            path_score = self.keyword_score(
                relative_str,
                keywords
            )

            content_score = self.keyword_score(
                content,
                keywords
            )

            structure_score = self.structure_score(relative_str)

            total_score = (
                path_score * 4
                + content_score
                + structure_score
            )

            if total_score > 0:
                results.append(
                    {
                        "file": relative_str,
                        "score": total_score,
                        "path_score": path_score,
                        "content_score": content_score,
                        "structure_score": structure_score,
                        "size": len(content),
                        "reason": "Keyword / structure match",
                    }
                )

        results.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        return results

    def structure_score(self, relative_path: str) -> int:
        lower_path = relative_path.lower()

        score = 0

        important_patterns = [
            "agent",
            "engine",
            "pipeline",
            "orchestrator",
            "provider",
            "router",
            "ui/app.py",
            "main.py",
        ]

        for pattern in important_patterns:
            if pattern in lower_path:
                score += 1

        return score

    # =========================================================
    # CLASSIFICATION
    # =========================================================

    def classify_files(
        self,
        affected_files: list,
        dependency_related_files: list
    ):
        core_files = []
        related_files = []
        context_files = []

        seen = set()

        combined = affected_files + dependency_related_files

        for item in combined:
            file_name = item["file"].replace("\\", "/")

            if file_name in seen:
                continue

            seen.add(file_name)

            first_dir = file_name.split("/")[0]

            if first_dir in self.context_dirs:
                context_files.append(item)
                continue

            if first_dir in self.core_dirs:
                core_files.append(item)
                continue

            related_files.append(item)

        core_files.sort(
            key=lambda item: item.get("score", 0),
            reverse=True
        )

        related_files.sort(
            key=lambda item: item.get("score", 0),
            reverse=True
        )

        context_files.sort(
            key=lambda item: item.get("score", 0),
            reverse=True
        )

        return core_files, related_files, context_files

    # =========================================================
    # RISK
    # =========================================================

    def estimate_risk(
        self,
        core_files: list,
        related_files: list,
        context_files: list
    ) -> str:
        risk_points = 0

        all_files = core_files + related_files + context_files

        for item in all_files:
            file_name = item["file"].lower()

            if file_name in ["main.py", "ui/app.py"]:
                risk_points += 5

            if "pipeline" in file_name:
                risk_points += 4

            if "orchestrator" in file_name:
                risk_points += 4

            if "provider" in file_name:
                risk_points += 3

            if "router" in file_name:
                risk_points += 3

            if "config" in file_name:
                risk_points += 2

            if "project_brain" in file_name:
                risk_points += 1

        if len(core_files) >= 15:
            risk_points += 5
        elif len(core_files) >= 8:
            risk_points += 3
        elif len(core_files) >= 4:
            risk_points += 1

        if risk_points >= 15:
            return "CRITICAL"

        if risk_points >= 9:
            return "HIGH"

        if risk_points >= 4:
            return "MEDIUM"

        return "LOW"

    # =========================================================
    # SUGGESTIONS
    # =========================================================

    def build_suggestions(self, user_goal: str) -> list:
        goal = user_goal.lower()

        suggestions = []

        if "seo" in goal:
            suggestions.extend(
                [
                    "Add SEO title scoring",
                    "Add keyword clustering",
                    "Add platform-specific SEO packages",
                    "Add thumbnail text generator",
                ]
            )

        if "trend" in goal or "niche" in goal:
            suggestions.extend(
                [
                    "Add niche-aware trend discovery",
                    "Add topic candidate ranking",
                    "Add duplicate topic prevention",
                    "Store used topics in topic_memory.json",
                ]
            )

        if "agent" in goal or "upgrade" in goal or "scan" in goal:
            suggestions.extend(
                [
                    "Keep ProjectUpgradeAgent in analyze-only mode first",
                    "Add approval state before file edits",
                    "Add backup creation before modifications",
                    "Add change report after modifications",
                    "Run verifier after modifications",
                ]
            )

        if "video" in goal or "pipeline" in goal:
            suggestions.extend(
                [
                    "Preserve provider router behavior",
                    "Add dry-run mode before expensive generation",
                    "Improve progress reporting",
                    "Avoid touching working Runway/Hailuo flow unless needed",
                ]
            )

        if not suggestions:
            suggestions.extend(
                [
                    "Start with targeted analysis",
                    "Confirm affected files",
                    "Create backup before any edit",
                    "Apply minimal changes only",
                    "Run verifier after change",
                ]
            )

        return suggestions

    # =========================================================
    # PROJECT BRAIN
    # =========================================================

    def collect_brain_context_status(self) -> dict:
        files = [
            "current_state.md",
            "dependency_map.md",
            "pipeline_map.md",
            "file_ownership.md",
            "impact_report.md",
            "CHAT_HANDOFF.md",
            "FULL_PROJECT_HANDOFF.md",
            "FULL_PROJECT_HANDOFF_NEW.md",
            "ACTIVE_PIPELINE.md",
            "SYSTEM_MAP.md",
            "EXECUTION_FLOW.md",
            "verification_report.md",
            "change_log.md",
        ]

        status = {}

        for file in files:
            content = self.read_brain_file(file)

            status[file] = {
                "exists": bool(content),
                "chars": len(content),
            }

        return status

    # =========================================================
    # PLAN GENERATION
    # =========================================================

    def generate_plan(
        self,
        user_goal: str,
        target_path: str = ""
    ) -> str:
        scanned_files = self.scan_target(target_path)

        raw_affected_files = self.analyze_files(
            scanned_files,
            user_goal
        )

        dependency_map = self.parse_dependency_map()

        dependency_related_files = self.find_dependency_related_files(
            raw_affected_files,
            dependency_map
        )

        core_files, related_files, context_files = self.classify_files(
            raw_affected_files,
            dependency_related_files
        )

        risk = self.estimate_risk(
            core_files,
            related_files,
            context_files
        )

        suggestions = self.build_suggestions(user_goal)
        brain_status = self.collect_brain_context_status()
        keywords = self.extract_keywords(user_goal)

        lines = []

        lines.append("# PROJECT UPGRADE AGENT PLAN")
        lines.append("")
        lines.append("Version: V2 - Targeted Analyze Mode")
        lines.append(
            f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append("")

        lines.append("## Mode")
        lines.append("")
        lines.append("ANALYZE ONLY")
        lines.append("")
        lines.append("- Automatic editing: DISABLED")
        lines.append("- Backup before edit: REQUIRED")
        lines.append("- User approval before edit: REQUIRED")
        lines.append("- Existing pipeline must be preserved")
        lines.append("- Runway / Hailuo / Provider Router must not be broken")
        lines.append("")

        lines.append("## User Goal")
        lines.append("")
        lines.append(user_goal)
        lines.append("")

        lines.append("## Extracted Keywords")
        lines.append("")

        if keywords:
            for keyword in keywords:
                lines.append(f"- {keyword}")
        else:
            lines.append("- No useful keywords detected")

        lines.append("")

        lines.append("## Scan Target")
        lines.append("")
        lines.append(target_path if target_path else "Full project")
        lines.append("")

        lines.append("## Scan Summary")
        lines.append("")
        lines.append(f"- Files scanned: {len(scanned_files)}")
        lines.append(
            f"- Raw keyword matches: {len(raw_affected_files)}"
        )
        lines.append(
            f"- Dependency related files: {len(dependency_related_files)}"
        )
        lines.append(f"- Core files: {len(core_files)}")
        lines.append(f"- Related files: {len(related_files)}")
        lines.append(f"- Context files: {len(context_files)}")
        lines.append(f"- Estimated risk: {risk}")
        lines.append("")

        lines.append("## Project Brain Context")
        lines.append("")

        for file, data in brain_status.items():
            status = "FOUND" if data["exists"] else "MISSING"

            lines.append(
                f"- {file}: {status} ({data['chars']} chars)"
            )

        lines.append("")

        lines.append("## Core Files")
        lines.append("")

        if core_files:
            for item in core_files[:20]:
                reason = item.get("reason", "")
                lines.append(
                    f"- {item['file']} "
                    f"| score={item.get('score', 0)} "
                    f"| reason={reason}"
                )
        else:
            lines.append("- None")

        lines.append("")

        lines.append("## Related Files")
        lines.append("")

        if related_files:
            for item in related_files[:20]:
                reason = item.get("reason", "")
                lines.append(
                    f"- {item['file']} "
                    f"| score={item.get('score', 0)} "
                    f"| reason={reason}"
                )
        else:
            lines.append("- None")

        lines.append("")

        lines.append("## Context Files")
        lines.append("")

        if context_files:
            for item in context_files[:20]:
                lines.append(
                    f"- {item['file']} "
                    f"| score={item.get('score', 0)}"
                )
        else:
            lines.append("- None")

        lines.append("")

        lines.append("## Suggested Improvements")
        lines.append("")

        for index, suggestion in enumerate(
            suggestions,
            start=1
        ):
            lines.append(f"{index}. {suggestion}")

        lines.append("")

        lines.append("## Recommended Safe Workflow")
        lines.append("")

        workflow = [
            "Review this upgrade plan",
            "Confirm core files",
            "Create project backup",
            "Apply changes only after explicit user approval",
            "Run verifier agent",
            "Run project scanner",
            "Update project_brain/current_state.md",
            "Generate new CHAT_HANDOFF.md",
        ]

        for index, step in enumerate(workflow, start=1):
            lines.append(f"{index}. {step}")

        lines.append("")

        lines.append("## Approval Status")
        lines.append("")
        lines.append("WAITING FOR USER APPROVAL")
        lines.append("")
        lines.append(
            "No file should be modified until user explicitly approves."
        )

        return "\n".join(lines)

    # =========================================================
    # SAVE / RUN
    # =========================================================

    def save_plan(self, plan: str) -> str:
        self.brain_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.output_file.write_text(
            plan,
            encoding="utf-8"
        )

        change_log = self.brain_dir / "change_log.md"

        with change_log.open(
            "a",
            encoding="utf-8"
        ) as file:
            file.write("\n\n")
            file.write(
                "## Project Upgrade Agent V2 Plan Generated\n"
            )
            file.write(
                f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            file.write(
                "- Output: project_brain/upgrade_plan.md\n"
            )

        return str(self.output_file)

    def run(
        self,
        user_goal: str,
        target_path: str = ""
    ) -> str:
        print("")
        print("=" * 70)
        print("MODIRAGENT PROJECT UPGRADE AGENT V2")
        print("=" * 70)
        print("")
        print(f"Goal: {user_goal}")
        print(f"Target: {target_path if target_path else 'Full project'}")
        print("")

        plan = self.generate_plan(
            user_goal=user_goal,
            target_path=target_path
        )

        output = self.save_plan(plan)

        print(f"Upgrade plan saved to: {output}")
        print("")
        print("Mode: ANALYZE ONLY")
        print("No files were modified.")
        print("")

        return output


def main():
    user_goal = (
        "Analyze project and suggest safe upgrade plan "
        "for project self-editing agent"
    )

    target_path = ""

    if len(sys.argv) >= 2:
        user_goal = sys.argv[1]

    if len(sys.argv) >= 3:
        target_path = sys.argv[2]

    agent = ProjectUpgradeAgent(".")

    agent.run(
        user_goal=user_goal,
        target_path=target_path
    )


if __name__ == "__main__":
    main()