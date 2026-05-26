from pathlib import Path
from datetime import datetime
import shutil


class SafeCodeEditor:
    """
    Safe Code Editor V1

    Purpose:
    - Create files safely
    - Append text safely
    - Replace exact text safely
    - Create backup before modification
    - Write change log

    Safety Rules:
    - No free automatic edits
    - No modification without explicit method call
    - Always backup existing files before editing
    """

    def __init__(self, project_root="."):
        self.project_root = Path(project_root).resolve()
        self.backup_dir = self.project_root / "storage" / "backups"
        self.brain_dir = self.project_root / "project_brain"
        self.change_log = self.brain_dir / "change_log.md"

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.brain_dir.mkdir(parents=True, exist_ok=True)

    def resolve_path(self, relative_path: str) -> Path:
        path = self.project_root / relative_path

        resolved = path.resolve()

        if not str(resolved).startswith(str(self.project_root)):
            raise ValueError("Blocked unsafe path outside project root.")

        return resolved

    def timestamp(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def create_backup(self, path: Path) -> str:
        if not path.exists():
            return ""

        backup_name = (
            str(path.relative_to(self.project_root))
            .replace("\\", "__")
            .replace("/", "__")
            + "."
            + self.timestamp()
            + ".bak"
        )

        backup_path = self.backup_dir / backup_name

        shutil.copy2(path, backup_path)

        return str(backup_path)

    def log_change(self, action: str, target: str, backup: str = "") -> None:
        with self.change_log.open("a", encoding="utf-8") as file:
            file.write("\n\n")
            file.write("## Safe Code Editor Change\n")
            file.write(f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            file.write(f"- Action: {action}\n")
            file.write(f"- Target: {target}\n")

            if backup:
                file.write(f"- Backup: {backup}\n")

    def create_file(
        self,
        relative_path: str,
        content: str,
        overwrite: bool = False
    ) -> str:
        path = self.resolve_path(relative_path)

        if path.exists() and not overwrite:
            raise FileExistsError(
                f"File already exists: {relative_path}"
            )

        backup = ""

        if path.exists():
            backup = self.create_backup(path)

        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content, encoding="utf-8")

        self.log_change(
            action="CREATE_FILE" if not backup else "OVERWRITE_FILE",
            target=relative_path,
            backup=backup
        )

        return str(path)

    def append_text(
        self,
        relative_path: str,
        text: str
    ) -> str:
        path = self.resolve_path(relative_path)

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {relative_path}"
            )

        backup = self.create_backup(path)

        with path.open("a", encoding="utf-8") as file:
            file.write(text)

        self.log_change(
            action="APPEND_TEXT",
            target=relative_path,
            backup=backup
        )

        return str(path)

    def replace_exact(
        self,
        relative_path: str,
        old_text: str,
        new_text: str
    ) -> str:
        path = self.resolve_path(relative_path)

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {relative_path}"
            )

        content = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        if old_text not in content:
            raise ValueError(
                "Exact text not found. No changes were made."
            )

        backup = self.create_backup(path)

        updated = content.replace(
            old_text,
            new_text,
            1
        )

        path.write_text(
            updated,
            encoding="utf-8"
        )

        self.log_change(
            action="REPLACE_EXACT",
            target=relative_path,
            backup=backup
        )

        return str(path)

    def dry_run_replace(
        self,
        relative_path: str,
        old_text: str
    ) -> bool:
        path = self.resolve_path(relative_path)

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {relative_path}"
            )

        content = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        return old_text in content


if __name__ == "__main__":
    editor = SafeCodeEditor(".")

    print("")
    print("=" * 60)
    print("MODIRAGENT SAFE CODE EDITOR")
    print("=" * 60)
    print("")
    print("SafeCodeEditor loaded successfully.")
    print("No changes were made.")
    print("")