from pathlib import Path
from datetime import datetime
import difflib


class PatchPreviewEngine:
    """
    Patch Preview Engine V1

    Purpose:
    - Preview file changes
    - Generate unified diff
    - No file modifications
    """

    def __init__(self, project_root="."):
        self.project_root = Path(project_root).resolve()

    def resolve_path(self, relative_path: str) -> Path:
        return (self.project_root / relative_path).resolve()

    def preview_append(
        self,
        relative_path: str,
        patch_text: str
    ) -> str:

        file_path = self.resolve_path(
            relative_path
        )

        if not file_path.exists():
            raise FileNotFoundError(
                relative_path
            )

        original = file_path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        modified = original + "\n\n" + patch_text

        diff = difflib.unified_diff(
            original.splitlines(),
            modified.splitlines(),
            fromfile=relative_path,
            tofile=relative_path,
            lineterm=""
        )

        return "\n".join(diff)

    def preview_replace(
        self,
        relative_path: str,
        old_text: str,
        new_text: str
    ) -> str:

        file_path = self.resolve_path(
            relative_path
        )

        if not file_path.exists():
            raise FileNotFoundError(
                relative_path
            )

        original = file_path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        modified = original.replace(
            old_text,
            new_text,
            1
        )

        diff = difflib.unified_diff(
            original.splitlines(),
            modified.splitlines(),
            fromfile=relative_path,
            tofile=relative_path,
            lineterm=""
        )

        return "\n".join(diff)

    def save_preview(
        self,
        preview_text: str
    ) -> str:

        output_dir = (
            self.project_root
            / "project_brain"
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        output_file = (
            output_dir
            / "patch_preview.md"
        )

        output_file.write_text(
            preview_text,
            encoding="utf-8"
        )

        return str(output_file)


if __name__ == "__main__":

    engine = PatchPreviewEngine(".")

    sample_patch = """
def retry_generation(
    operation,
    retries=3
):
    pass
"""

    preview = engine.preview_append(
        "providers/runway_video_provider.py",
        sample_patch
    )

    path = engine.save_preview(
        preview
    )

    print("")
    print("=" * 60)
    print("PATCH PREVIEW GENERATED")
    print("=" * 60)
    print("")
    print(path)
    print("")