import os
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(".")
OUTPUT_FILE = PROJECT_ROOT / "project_brain" / "FULL_PROJECT_HANDOFF.md"

IGNORE_FOLDERS = {
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
}

IGNORE_FILES_CONTAINS = {
    ".log",
    ".tmp",
}

IMPORTANT_EXTENSIONS = {
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
}


def should_ignore(path: Path):
    for part in path.parts:
        if part in IGNORE_FOLDERS:
            return True

    filename = path.name.lower()

    for item in IGNORE_FILES_CONTAINS:
        if item in filename:
            return True

    return False


def detect_file_purpose(file_path: Path, content: str):
    name = file_path.name.lower()
    content_lower = content.lower()

    if "test_" in name:
        return "Test / debug pipeline"

    if "full_selfcare_factory" in name:
        return "Main AI selfcare video factory pipeline"

    if "orchestrator" in name:
        return "Pipeline orchestration system"

    if "provider" in name:
        return "AI provider integration"

    if "subtitle" in name:
        return "Subtitle generation / subtitle burning"

    if "thumbnail" in name:
        return "Thumbnail generation"

    if "hook" in name:
        return "Viral hook optimization"

    if "music" in name:
        return "Background music processing"

    if "audio" in name:
        return "Audio processing system"

    if "seo" in name:
        return "SEO package generation"

    if "memory" in name:
        return "AI memory / learning system"

    if "optimization" in name:
        return "Optimization system"

    if "publishing" in name:
        return "Publishing/export system"

    if "timeline" in name:
        return "Timeline sequencing system"

    if "continuity" in name:
        return "Scene continuity system"

    if "director" in name:
        return "AI directing / cinematic system"

    if "ffmpeg" in content_lower:
        return "FFmpeg video/audio processing"

    if "openai" in content_lower:
        return "OpenAI integration"

    if "elevenlabs" in content_lower:
        return "ElevenLabs voice generation"

    if "hailuo" in content_lower:
        return "Hailuo AI video generation"

    if "tkinter" in content_lower:
        return "Desktop user interface"

    return "General project component"


def read_file_preview(file_path: Path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read(2500)
    except Exception:
        return ""


def scan_project():
    results = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        root_path = Path(root)

        dirs[:] = [
            d for d in dirs
            if d not in IGNORE_FOLDERS
        ]

        if should_ignore(root_path):
            continue

        for file in files:
            file_path = root_path / file

            if should_ignore(file_path):
                continue

            if file_path.suffix.lower() not in IMPORTANT_EXTENSIONS:
                continue

            try:
                size_kb = round(file_path.stat().st_size / 1024, 2)
            except Exception:
                size_kb = 0

            preview = read_file_preview(file_path)

            purpose = detect_file_purpose(
                file_path,
                preview
            )

            results.append({
                "path": str(file_path),
                "size_kb": size_kb,
                "purpose": purpose,
                "preview": preview[:1000],
            })

    return results


def build_summary(results):
    summary = {
        "providers": [],
        "engines": [],
        "agents": [],
        "core_systems": [],
        "configs": [],
        "ui": [],
        "tests": [],
    }

    for item in results:
        path = item["path"].lower()

        if "providers/" in path or "providers\\" in path:
            summary["providers"].append(item["path"])

        elif "engines/" in path or "engines\\" in path:
            summary["engines"].append(item["path"])

        elif "agents/" in path or "agents\\" in path:
            summary["agents"].append(item["path"])

        elif "core/" in path or "core\\" in path:
            summary["core_systems"].append(item["path"])

        elif "config/" in path or "config\\" in path:
            summary["configs"].append(item["path"])

        elif "ui/" in path or "ui\\" in path:
            summary["ui"].append(item["path"])

        if "test_" in path:
            summary["tests"].append(item["path"])

    return summary


def read_brain_reports():
    reports = {}

    report_files = [
        "SYSTEM_MAP.md",
        "ACTIVE_PIPELINE.md",
        "EXECUTION_FLOW.md",
        "DEAD_FILES_REPORT.md",
        "CHAT_HANDOFF.md",
        "current_state.md",
        "roadmap.md",
        "next_steps.md",
        "known_issues.md",
        "pipeline_map.md",
        "dependency_map.md",
        "impact_report.md",
        "memory_snapshot.md",
        "verification_report.md",
    ]

    for report in report_files:
        report_path = PROJECT_ROOT / "project_brain" / report

        if report_path.exists():
            try:
                reports[report] = report_path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            except Exception as e:
                reports[report] = f"ERROR READING REPORT: {e}"

    return reports


def build_handoff(results, summary):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []

    lines.append("# FULL PROJECT HANDOFF")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")

    lines.append("## PROJECT STATUS")
    lines.append("")
    lines.append("Project: ModirAgentOS - Autonomous AI Selfcare Video Factory")
    lines.append("")
    lines.append("Purpose: AI-powered automated short-form skincare/selfcare content factory.")
    lines.append("")

    lines.append("Current Direction:")
    lines.append("- Trend discovery")
    lines.append("- SEO generation")
    lines.append("- AI narration")
    lines.append("- Hailuo video generation")
    lines.append("- Clip synchronization")
    lines.append("- Subtitle burn")
    lines.append("- Music system")
    lines.append("- Hook overlay")
    lines.append("- Ingredient overlay")
    lines.append("- Thumbnail generation")
    lines.append("- Publishing package")
    lines.append("- AI memory learning")
    lines.append("")

    lines.append("## IMPORTANT SYSTEMS")
    lines.append("")
    lines.append(f"Providers detected: {len(summary['providers'])}")
    lines.append(f"Engines detected: {len(summary['engines'])}")
    lines.append(f"Agents detected: {len(summary['agents'])}")
    lines.append(f"Core systems detected: {len(summary['core_systems'])}")
    lines.append(f"Config files detected: {len(summary['configs'])}")
    lines.append(f"UI files detected: {len(summary['ui'])}")
    lines.append(f"Test/debug files detected: {len(summary['tests'])}")
    lines.append("")

    lines.append("## MAIN EXECUTION FILES")
    lines.append("")
    important_files = [
        "main.py",
        "full_selfcare_factory.py",
        "test_full_ai_video_pipeline.py",
        "ui/app.py",
        "core/master_orchestrator_engine.py",
        "core/project_brain_engine.py",
        "core/full_project_scanner.py",
    ]

    for file in important_files:
        lines.append(f"- {file}")

    lines.append("")

    lines.append("## IMPORTANT COMMANDS")
    lines.append("")
    lines.append("Run main menu:")
    lines.append("```powershell")
    lines.append("python main.py")
    lines.append("```")
    lines.append("")

    lines.append("Run full AI pipeline:")
    lines.append("```powershell")
    lines.append("python test_full_ai_video_pipeline.py")
    lines.append("```")
    lines.append("")

    lines.append("Run UI:")
    lines.append("```powershell")
    lines.append("python ui/app.py")
    lines.append("```")
    lines.append("")

    lines.append("Run project brain engine:")
    lines.append("```powershell")
    lines.append("python -m core.project_brain_engine")
    lines.append("```")
    lines.append("")

    lines.append("Run full scanner:")
    lines.append("```powershell")
    lines.append("python -m core.full_project_scanner")
    lines.append("```")
    lines.append("")

    lines.append("Package-based execution rule:")
    lines.append("```powershell")
    lines.append("python -m module_name")
    lines.append("```")
    lines.append("")

    lines.append("## CURRENT KNOWN ISSUE")
    lines.append("")
    lines.append("- Trend topic repetition was fixed in test_full_ai_video_pipeline.py with random fallback topics.")
    lines.append("- Next improvement: add used_topics memory system so repeated topics are rejected automatically.")
    lines.append("")

    lines.append("## NEXT STEP")
    lines.append("")
    lines.append("- Add used_topics.txt or JSON memory for generated topics.")
    lines.append("- Reject repeated topics automatically.")
    lines.append("- Make OpenAI trend generation read previous topics.")
    lines.append("- Improve SelfcareContentEngine so recipe/voiceover adapts to each new topic, not only yogurt/honey/oat.")
    lines.append("- Integrate advanced Project Brain reports into normal workflow.")
    lines.append("")

    reports = read_brain_reports()

    if reports:
        lines.append("## ADVANCED PROJECT BRAIN")
        lines.append("")

        for report_name, content in reports.items():
            lines.append("---")
            lines.append("")
            lines.append(f"### {report_name}")
            lines.append("")
            lines.append("```")
            lines.append(content[:12000])
            lines.append("```")
            lines.append("")

    lines.append("## FILE MAP")
    lines.append("")

    for item in results:
        lines.append("---")
        lines.append("")
        lines.append(f"### FILE: `{item['path']}`")
        lines.append("")
        lines.append(f"Purpose: {item['purpose']}")
        lines.append("")
        lines.append(f"Size: {item['size_kb']} KB")

        preview = item["preview"].strip()

        if preview:
            lines.append("")
            lines.append("Preview:")
            lines.append("```")
            lines.append(preview)
            lines.append("```")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("# END OF HANDOFF")

    return "\n".join(lines)


def save_handoff(content):
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(content)


def main():
    print("\n" + "=" * 80)
    print("SMART FULL PROJECT SCANNER + PROJECT BRAIN MERGER")
    print("=" * 80)

    print("\n[1] Scanning project...")
    results = scan_project()

    print(f"[OK] Files scanned: {len(results)}")

    print("\n[2] Building summary...")
    summary = build_summary(results)

    print("\n[3] Reading project brain reports...")
    reports = read_brain_reports()
    print(f"[OK] Brain reports found: {len(reports)}")

    print("\n[4] Building final handoff...")
    handoff = build_handoff(results, summary)

    print("\n[5] Saving final handoff...")
    save_handoff(handoff)

    print("\n" + "=" * 80)
    print("FINAL HANDOFF COMPLETE")
    print("=" * 80)

    print(f"\nSaved to:\n{OUTPUT_FILE}")


if __name__ == "__main__":
    main()