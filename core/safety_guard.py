from pathlib import Path


BLOCKED_DIRS = {
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    "outputs",
    "node_modules",
}

BLOCKED_FILES = {
    ".env",
    "secrets.yaml",
    "credentials.json",
    "api_keys.txt",
}

ALLOWED_CODE_EXTENSIONS = {
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
}


def is_inside_blocked_dir(file_path: Path) -> bool:
    return any(part in BLOCKED_DIRS for part in file_path.parts)


def is_blocked_file(file_path: Path) -> bool:
    return file_path.name in BLOCKED_FILES


def has_allowed_extension(file_path: Path) -> bool:
    return file_path.suffix.lower() in ALLOWED_CODE_EXTENSIONS


def validate_file_change(target_file: str, project_root: str = ".") -> tuple[bool, str]:
    root = Path(project_root).resolve()
    file_path = (root / target_file).resolve()

    try:
        file_path.relative_to(root)
    except ValueError:
        return False, "Blocked: target file is outside project root."

    if is_inside_blocked_dir(file_path):
        return False, "Blocked: target file is inside a protected folder."

    if is_blocked_file(file_path):
        return False, "Blocked: target file is sensitive and must not be edited."

    if not has_allowed_extension(file_path):
        return False, "Blocked: file extension is not allowed for automated edits."

    return True, "Allowed: file change passed safety checks."


if __name__ == "__main__":
    test_files = [
        "main.py",
        "core/project_scanner.py",
        ".env",
        "venv/test.py",
        "../outside.py",
        "project_brain/current_state.md",
    ]

    for file in test_files:
        allowed, message = validate_file_change(file)
        print(f"{file}: {message}")