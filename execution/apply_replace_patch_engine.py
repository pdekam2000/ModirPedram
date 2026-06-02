from pathlib import Path
from execution.replace_patch_engine import ReplacePatchEngine
from execution.rollback_manager import create_backup

class ApplyReplacePatchEngine:

    """
    Applies validated replace-function patches safely.

    Workflow:
    - Build patch preview
    - Create backup
    - Apply replacement
    - Save updated file
    """

    def __init__(self, project_root="."):

        self.project_root = Path(project_root).resolve()

        self.patch_engine = ReplacePatchEngine(
            project_root
        )

    def apply_replace_patch(
        self,
        file_path,
        function_name,
        new_function_source,
        class_name=None,
        approve=False
    ):

        patch = self.patch_engine.build_replace_patch(
            file_path=file_path,
            function_name=function_name,
            class_name=class_name,
            new_function_source=new_function_source
        )

        if not approve:

            return {
                "status": "WAITING_APPROVAL",
                "patch": patch
            }

        backup_result = create_backup(
            target_file=file_path,
            project_root=str(self.project_root)
        )

        if not backup_result.get("success"):

            return {
                "status": "BACKUP_FAILED",
                "message": backup_result.get("message"),
                "patch": patch
            }

        target_path = Path(file_path)

        if not target_path.is_absolute():

            target_path = (
                self.project_root / target_path
            )

        target_path.write_text(
            patch["updated_source"],
            encoding="utf-8"
        )

        return {
            "status": "PATCH_APPLIED",
            "file_path": str(target_path),
            "backup_path": backup_result.get("backup_path"),
            "function_name": function_name,
            "class_name": class_name,
            "patch": patch
        }


if __name__ == "__main__":

    engine = ApplyReplacePatchEngine(".")

    test_file = (
        "execution/"
        "apply_replace_patch_test_target.py"
    )

    Path(test_file).write_text(
        '''class Demo:

    def demo_replace_target(self):

        print("OLD VERSION")

        return False
''',
        encoding="utf-8"
    )

    new_function = '''
def demo_replace_target(self):

    print("REAL FILE REPLACED SUCCESSFULLY")

    return True
'''

    preview = engine.apply_replace_patch(
        file_path=test_file,
        function_name="demo_replace_target",
        class_name="Demo",
        new_function_source=new_function,
        approve=False
    )

    print("\n" + "=" * 60)
    print("PREVIEW MODE")
    print("=" * 60)

    print(preview["patch"]["diff_preview"])

    applied = engine.apply_replace_patch(
        file_path=test_file,
        function_name="demo_replace_target",
        class_name="Demo",
        new_function_source=new_function,
        approve=True
    )

    print("\n" + "=" * 60)
    print("PATCH APPLIED")
    print("=" * 60)

    print(
        f"\nStatus:\n"
        f"{applied['status']}"
    )

    print(
        f"\nBackup created:\n"
        f"{applied.get('backup_path')}"
    )

    print(
        f"\nUpdated file:\n"
        f"{applied.get('file_path')}"
    )

    print("\n" + "=" * 60)
    print("FINAL FILE CONTENT")
    print("=" * 60)

    print(
        Path(test_file).read_text(
            encoding="utf-8"
        )
    )