import json
import zipfile
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRAIN_DIR = PROJECT_ROOT / "project_brain"
RUNTIME_STATE_DIR = BRAIN_DIR / "runtime_state"

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

BACKUP_NAME = f"PROJECT_BACKUP_{TIMESTAMP}.zip"
BACKUP_PATH = BRAIN_DIR / BACKUP_NAME

MANIFEST_PATH = BRAIN_DIR / "backup_manifest.json"
REPORT_PATH = BRAIN_DIR / "latest_backup_report.md"

EXCLUDE_DIRS = {
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}

EXCLUDE_FILES = {
    ".env",
    ".env.local",
    ".env.production",
}

EXCLUDE_SUFFIXES = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".tmp",
    ".pyc",
    ".log",
}


def should_exclude(path: Path) -> bool:
    parts = set(path.parts)

    if parts & EXCLUDE_DIRS:
        return True

    if path.name in EXCLUDE_FILES:
        return True

    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return True

    if path.name.startswith("PROJECT_BACKUP_") and path.suffix == ".zip":
        return True

    return False


def scan_project():
    files = []
    folders = set()

    for path in PROJECT_ROOT.rglob("*"):
        if should_exclude(path):
            continue

        rel_path = path.relative_to(PROJECT_ROOT)

        if path.is_dir():
            folders.add(str(rel_path))
        else:
            files.append(str(rel_path))

    return sorted(files), sorted(folders)


def categorize_files(files):
    categories = {
        "agents": [],
        "core": [],
        "execution": [],
        "ui": [],
        "providers": [],
        "pipelines": [],
        "config": [],
        "tasks": [],
        "templates": [],
        "storage": [],
        "project_brain": [],
        "runtime_state": [],
        "topic_memory": [],
        "other": [],
    }

    for file in files:
        normalized = file.replace("\\", "/")

        if normalized.startswith("agents/"):
            categories["agents"].append(file)
        elif normalized.startswith("core/"):
            categories["core"].append(file)
        elif normalized.startswith("execution/"):
            categories["execution"].append(file)
        elif normalized.startswith("ui/"):
            categories["ui"].append(file)
        elif normalized.startswith("providers/"):
            categories["providers"].append(file)
        elif normalized.startswith("pipelines/"):
            categories["pipelines"].append(file)
        elif normalized.startswith("config/"):
            categories["config"].append(file)
        elif normalized.startswith("tasks/"):
            categories["tasks"].append(file)
        elif normalized.startswith("templates/"):
            categories["templates"].append(file)
        elif normalized.startswith("storage/"):
            categories["storage"].append(file)
        elif normalized.startswith("project_brain/runtime_state/"):
            categories["runtime_state"].append(file)
        elif normalized.startswith("project_brain/topic_memory/"):
            categories["topic_memory"].append(file)
        elif normalized.startswith("project_brain/"):
            categories["project_brain"].append(file)
        else:
            categories["other"].append(file)

    return categories


def read_runtime_state_summary():
    if not RUNTIME_STATE_DIR.exists():
        return {
            "status": "No runtime_state directory found.",
            "latest_file": None,
        }

    state_files = list(RUNTIME_STATE_DIR.glob("*.json"))

    if not state_files:
        return {
            "status": "runtime_state exists, but no JSON files found.",
            "latest_file": None,
        }

    latest_file = max(state_files, key=lambda p: p.stat().st_mtime)

    try:
        data = json.loads(latest_file.read_text(encoding="utf-8"))
    except Exception as error:
        return {
            "status": "Could not read runtime state.",
            "latest_file": latest_file.name,
            "error": str(error),
        }

    return {
        "status": "Runtime state loaded.",
        "latest_file": latest_file.name,
        "session_id": data.get("session_id"),
        "runtime_status": data.get("runtime_status"),
        "current_step": data.get("current_step"),
        "updated_at": data.get("updated_at"),
        "approval_metadata": data.get("approval_metadata"),
    }


def build_full_handoff(files, folders, categories, runtime_summary):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    runtime_json = json.dumps(runtime_summary, indent=2, ensure_ascii=False)

    lines = []

    lines.append("# ModirAgentOS - Full Project Handoff")
    lines.append("")
    lines.append(f"Generated at: `{now}`")
    lines.append("")
    lines.append("## Current Milestone")
    lines.append("")
    lines.append("Runtime Editing V1 is working.")
    lines.append("")
    lines.append("## Recently Completed")
    lines.append("")
    lines.append("- `ui/runtime_studio_app.py` created as separate Developer/Admin app.")
    lines.append("- Runtime Studio V2 works separately from main app.")
    lines.append("- Structured text command flow works.")
    lines.append("- `core/runtime_command_parser.py` created.")
    lines.append("- `agents/runtime_patch_generator_agent.py` created.")
    lines.append("- FunctionExtractor connected to Runtime Studio.")
    lines.append("- Real function `old_source` is passed into patch generator.")
    lines.append("- Text command -> Parser -> Function Extract -> Patch Generator -> Diff Preview -> Approve -> Real Apply -> Verifier works.")
    lines.append("- Tested commands:")
    lines.append("  - Change print message to ...")
    lines.append("  - Add try except")
    lines.append("  - Add logging")
    lines.append("- Real apply, backup, verifier, and approval gate all work.")
    lines.append("")
    lines.append("## Automatic Brain + Backup System")
    lines.append("")
    lines.append("Main script:")
    lines.append("")
    lines.append("`project_brain/auto_handoff_backup.py`")
    lines.append("")
    lines.append("Run command:")
    lines.append("")
    lines.append("`python -m project_brain.auto_handoff_backup`")
    lines.append("")
    lines.append("## Runtime State Summary")
    lines.append("")
    lines.append("```json")
    lines.append(runtime_json)
    lines.append("```")
    lines.append("")
    lines.append("## Project Scan Summary")
    lines.append("")
    lines.append(f"- Total folders detected: `{len(folders)}`")
    lines.append(f"- Total files detected: `{len(files)}`")
    lines.append("")

    for category, items in categories.items():
        lines.append(f"## Detected {category}")
        lines.append("")

        if items:
            for item in items:
                lines.append(f"- `{item}`")
        else:
            lines.append("- None detected")

        lines.append("")

    lines.append("## Backup Rules")
    lines.append("")
    lines.append("Included:")
    lines.append("")
    lines.append("- code files")
    lines.append("- project_brain files")
    lines.append("- runtime_state")
    lines.append("- topic_memory")
    lines.append("- config files")
    lines.append("- providers")
    lines.append("- pipelines")
    lines.append("- UI files")
    lines.append("- important storage metadata")
    lines.append("")
    lines.append("Excluded:")
    lines.append("")
    lines.append("- `.env`")
    lines.append("- `venv` / `.venv`")
    lines.append("- `__pycache__`")
    lines.append("- `.git`")
    lines.append("- large generated videos")
    lines.append("- temp/cache/log files")
    lines.append("- old generated `PROJECT_BACKUP_*.zip` files")
    lines.append("")
    lines.append("## Next Steps")
    lines.append("")
    lines.append("1. Run this script after every major change.")
    lines.append("2. Check `project_brain/latest_backup_report.md`.")
    lines.append("3. Check `project_brain/backup_manifest.json`.")
    lines.append("4. Later add Runtime Studio button: `Update Brain + Create Backup`.")
    lines.append("")

    return "\n".join(lines)


def build_chat_handoff():
    lines = []

    lines.append("# ModirAgentOS - Chat Handoff")
    lines.append("")
    lines.append("Current milestone:")
    lines.append("Runtime Editing V1 is working.")
    lines.append("")
    lines.append("Recently completed:")
    lines.append("- Runtime Studio V2 works as separate Developer/Admin app.")
    lines.append("- Structured text command flow works.")
    lines.append("- RuntimeCommandParser created.")
    lines.append("- RuntimePatchGeneratorAgent created.")
    lines.append("- FunctionExtractor connected to Runtime Studio.")
    lines.append("- Real old_source is passed into patch generator.")
    lines.append("- Text command -> Parser -> Function Extract -> Patch Generator -> Diff Preview -> Approve -> Real Apply -> Verifier works.")
    lines.append("- Tested commands:")
    lines.append("  - Change print message to ...")
    lines.append("  - Add try except")
    lines.append("  - Add logging")
    lines.append("- Real apply, backup, verifier, and approval gate all work.")
    lines.append("")
    lines.append("Current new system:")
    lines.append("Automatic Project Brain + Full Handoff + Backup system.")
    lines.append("")
    lines.append("Main script:")
    lines.append("project_brain/auto_handoff_backup.py")
    lines.append("")
    lines.append("Run:")
    lines.append("python -m project_brain.auto_handoff_backup")
    lines.append("")
    lines.append("Generated files:")
    lines.append("- project_brain/FULL_PROJECT_HANDOFF.md")
    lines.append("- project_brain/CHAT_HANDOFF.md")
    lines.append("- project_brain/current_state.md")
    lines.append("- project_brain/SYSTEM_MAP.md")
    lines.append("- project_brain/EXECUTION_FLOW.md")
    lines.append("- project_brain/ACTIVE_PIPELINE.md")
    lines.append("- project_brain/change_log.md")
    lines.append("- project_brain/next_steps.md")
    lines.append("- project_brain/backup_manifest.json")
    lines.append("- project_brain/latest_backup_report.md")
    lines.append("- project_brain/PROJECT_BACKUP_YYYYMMDD_HHMMSS.zip")
    lines.append("")
    lines.append("Important safety rule:")
    lines.append("Preserve previous settings. Do not rewrite unrelated files. Work step-by-step only.")
    lines.append("")

    return "\n".join(lines)


def build_current_state(files, folders, runtime_summary):
    runtime_json = json.dumps(runtime_summary, indent=2, ensure_ascii=False)

    lines = []

    lines.append("# Current State")
    lines.append("")
    lines.append(f"Generated: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
    lines.append("")
    lines.append("## Status")
    lines.append("")
    lines.append("Runtime Editing V1 is working.")
    lines.append("")
    lines.append("## Project Size")
    lines.append("")
    lines.append(f"- Folders: `{len(folders)}`")
    lines.append(f"- Files: `{len(files)}`")
    lines.append("")
    lines.append("## Runtime Summary")
    lines.append("")
    lines.append("```json")
    lines.append(runtime_json)
    lines.append("```")
    lines.append("")
    lines.append("## Latest Completed Work")
    lines.append("")
    lines.append("Automatic Project Brain + Full Handoff + Backup script added:")
    lines.append("")
    lines.append("`project_brain/auto_handoff_backup.py`")
    lines.append("")

    return "\n".join(lines)


def build_system_map(categories):
    lines = []

    lines.append("# System Map")
    lines.append("")

    for category, items in categories.items():
        lines.append(f"## {category}")
        lines.append("")

        if items:
            for item in items:
                lines.append(f"- `{item}`")
        else:
            lines.append("- None detected")

        lines.append("")

    return "\n".join(lines)


def build_execution_flow():
    lines = []

    lines.append("# Execution Flow")
    lines.append("")
    lines.append("## Runtime Editing V1")
    lines.append("")
    lines.append("Text Command")
    lines.append("-> RuntimeCommandParser")
    lines.append("-> FunctionExtractor")
    lines.append("-> RuntimePatchGeneratorAgent")
    lines.append("-> Diff Preview")
    lines.append("-> Approval Gate")
    lines.append("-> Real Apply")
    lines.append("-> Backup")
    lines.append("-> Verifier")
    lines.append("")
    lines.append("## Brain + Backup Flow")
    lines.append("")
    lines.append("Run:")
    lines.append("")
    lines.append("`python -m project_brain.auto_handoff_backup`")
    lines.append("")
    lines.append("Then:")
    lines.append("")
    lines.append("Project Scan")
    lines.append("-> Read Runtime State")
    lines.append("-> Generate FULL_PROJECT_HANDOFF.md")
    lines.append("-> Generate CHAT_HANDOFF.md")
    lines.append("-> Update current_state.md")
    lines.append("-> Update SYSTEM_MAP.md")
    lines.append("-> Update EXECUTION_FLOW.md")
    lines.append("-> Update ACTIVE_PIPELINE.md")
    lines.append("-> Update next_steps.md")
    lines.append("-> Append change_log.md")
    lines.append("-> Create backup ZIP")
    lines.append("-> Create backup_manifest.json")
    lines.append("-> Create latest_backup_report.md")
    lines.append("")

    return "\n".join(lines)


def build_active_pipeline():
    lines = []

    lines.append("# Active Pipeline")
    lines.append("")
    lines.append("## Active Development Pipeline")
    lines.append("")
    lines.append("Runtime Editing V1 is currently active.")
    lines.append("")
    lines.append("## Working Flow")
    lines.append("")
    lines.append("Text command -> Parser -> Extract Function -> Generate Patch -> Preview Diff -> Approve -> Apply -> Verify")
    lines.append("")
    lines.append("## Maintenance Flow")
    lines.append("")
    lines.append("After every major project change, run:")
    lines.append("")
    lines.append("`python -m project_brain.auto_handoff_backup`")
    lines.append("")
    lines.append("This refreshes the project brain and creates a backup.")
    lines.append("")

    return "\n".join(lines)


def build_next_steps():
    lines = []

    lines.append("# Next Steps")
    lines.append("")
    lines.append("1. Run the automatic handoff + backup script.")
    lines.append("2. Confirm backup ZIP is created.")
    lines.append("3. Confirm `backup_manifest.json` is created.")
    lines.append("4. Confirm `latest_backup_report.md` is created.")
    lines.append("5. Later add Runtime Studio button: `Update Brain + Create Backup`.")
    lines.append("")

    return "\n".join(lines)


def append_change_log():
    change_log_path = BRAIN_DIR / "change_log.md"

    lines = []
    lines.append("")
    lines.append("")
    lines.append("## Auto Handoff + Backup Update")
    lines.append("")
    lines.append(f"- Timestamp: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
    lines.append("- Project scan completed.")
    lines.append("- Runtime state summary saved.")
    lines.append("- Handoff files refreshed.")
    lines.append("- Backup ZIP generated.")
    lines.append("")

    entry = "\n".join(lines)

    if change_log_path.exists():
        old_text = change_log_path.read_text(encoding="utf-8", errors="ignore")
        change_log_path.write_text(old_text + entry, encoding="utf-8")
    else:
        change_log_path.write_text("# Change Log\n" + entry, encoding="utf-8")


def write_brain_files(
    full_handoff,
    chat_handoff,
    current_state,
    system_map,
    execution_flow,
    active_pipeline,
    next_steps,
):
    BRAIN_DIR.mkdir(exist_ok=True)

    (BRAIN_DIR / "FULL_PROJECT_HANDOFF.md").write_text(
        full_handoff,
        encoding="utf-8",
    )

    (BRAIN_DIR / "CHAT_HANDOFF.md").write_text(
        chat_handoff,
        encoding="utf-8",
    )

    (BRAIN_DIR / "current_state.md").write_text(
        current_state,
        encoding="utf-8",
    )

    (BRAIN_DIR / "SYSTEM_MAP.md").write_text(
        system_map,
        encoding="utf-8",
    )

    (BRAIN_DIR / "EXECUTION_FLOW.md").write_text(
        execution_flow,
        encoding="utf-8",
    )

    (BRAIN_DIR / "ACTIVE_PIPELINE.md").write_text(
        active_pipeline,
        encoding="utf-8",
    )

    (BRAIN_DIR / "next_steps.md").write_text(
        next_steps,
        encoding="utf-8",
    )

    append_change_log()


def create_backup(files):
    backed_up = []

    with zipfile.ZipFile(BACKUP_PATH, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in files:
            abs_path = PROJECT_ROOT / file

            if not abs_path.exists():
                continue

            if should_exclude(abs_path):
                continue

            zipf.write(abs_path, file)
            backed_up.append(file)

    return backed_up


def write_manifest(backed_up):
    manifest = {
        "created_at": datetime.now().isoformat(),
        "backup_file": BACKUP_NAME,
        "backup_path": str(BACKUP_PATH),
        "project_root": str(PROJECT_ROOT),
        "total_files": len(backed_up),
        "excluded_dirs": sorted(EXCLUDE_DIRS),
        "excluded_files": sorted(EXCLUDE_FILES),
        "excluded_suffixes": sorted(EXCLUDE_SUFFIXES),
        "files": backed_up,
    }

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_backup_report(backed_up):
    lines = []

    lines.append("# Latest Backup Report")
    lines.append("")
    lines.append(f"- Backup file: `{BACKUP_NAME}`")
    lines.append(f"- Created at: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
    lines.append(f"- Total files included: `{len(backed_up)}`")
    lines.append("")
    lines.append("## Backup Location")
    lines.append("")
    lines.append(f"`{BACKUP_PATH}`")
    lines.append("")
    lines.append("## Excluded")
    lines.append("")
    lines.append("- `.env`")
    lines.append("- `venv`")
    lines.append("- `.venv`")
    lines.append("- `__pycache__`")
    lines.append("- `.git`")
    lines.append("- generated videos")
    lines.append("- temp/cache/log files")
    lines.append("- old `PROJECT_BACKUP_*.zip` files")
    lines.append("")
    lines.append("## Status")
    lines.append("")
    lines.append("Backup completed successfully.")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main():
    print("")
    print("[Auto Handoff Backup] Starting...")

    files, folders = scan_project()
    categories = categorize_files(files)
    runtime_summary = read_runtime_state_summary()

    full_handoff = build_full_handoff(
        files=files,
        folders=folders,
        categories=categories,
        runtime_summary=runtime_summary,
    )

    chat_handoff = build_chat_handoff()
    current_state = build_current_state(files, folders, runtime_summary)
    system_map = build_system_map(categories)
    execution_flow = build_execution_flow()
    active_pipeline = build_active_pipeline()
    next_steps = build_next_steps()

    write_brain_files(
        full_handoff=full_handoff,
        chat_handoff=chat_handoff,
        current_state=current_state,
        system_map=system_map,
        execution_flow=execution_flow,
        active_pipeline=active_pipeline,
        next_steps=next_steps,
    )

    files_after_update, _ = scan_project()
    backed_up = create_backup(files_after_update)

    write_manifest(backed_up)
    write_backup_report(backed_up)

    print("")
    print("[Auto Handoff Backup] Completed.")
    print(f"Backup created: {BACKUP_PATH}")
    print(f"Files included: {len(backed_up)}")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()