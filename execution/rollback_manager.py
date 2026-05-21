from pathlib import Path
from datetime import datetime
import shutil


BACKUP_DIR = "storage/backups"


def create_backup(target_file: str, project_root: str = ".") -> dict:
    root = Path(project_root).resolve()
    source = (root / target_file).resolve()

    if not source.exists():
        return {
            "success": False,
            "message": "Backup failed: target file does not exist.",
            "backup_path": None,
        }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = root / BACKUP_DIR
    backup_root.mkdir(parents=True, exist_ok=True)

    safe_name = target_file.replace("\\", "__").replace("/", "__")
    backup_path = backup_root / f"{safe_name}.{timestamp}.bak"

    shutil.copy2(source, backup_path)

    return {
        "success": True,
        "message": "Backup created successfully.",
        "backup_path": str(backup_path),
    }


def restore_backup(backup_path: str, target_file: str, project_root: str = ".") -> dict:
    root = Path(project_root).resolve()
    backup = Path(backup_path).resolve()
    target = (root / target_file).resolve()

    if not backup.exists():
        return {
            "success": False,
            "message": "Restore failed: backup file does not exist.",
        }

    shutil.copy2(backup, target)

    return {
        "success": True,
        "message": "Backup restored successfully.",
    }


if __name__ == "__main__":
    result = create_backup("main.py")
    print(result)