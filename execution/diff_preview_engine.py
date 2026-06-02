import difflib
from pathlib import Path


class DiffPreviewEngine:

    """
    Creates safe unified diff previews before applying changes.
    Does not modify files.
    """

    def __init__(self, project_root="."):

        self.project_root = Path(project_root).resolve()

    def build_diff(
        self,
        old_source,
        new_source,
        from_label="OLD",
        to_label="NEW"
    ):

        if not old_source.endswith("\n"):
            old_source += "\n"

        if not new_source.endswith("\n"):
            new_source += "\n"

        old_lines = old_source.splitlines(keepends=True)
        new_lines = new_source.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=from_label,
            tofile=to_label
        )

        return "".join(diff).strip()

    def preview_function_replace(
        self,
        old_function_source,
        new_function_source,
        file_path=None,
        function_name=None
    ):

        from_label = "OLD_FUNCTION"
        to_label = "NEW_FUNCTION"

        if file_path and function_name:

            from_label = (
                f"{file_path}::{function_name} OLD"
            )

            to_label = (
                f"{file_path}::{function_name} NEW"
            )

        return self.build_diff(
            old_source=old_function_source,
            new_source=new_function_source,
            from_label=from_label,
            to_label=to_label
        )


if __name__ == "__main__":

    engine = DiffPreviewEngine(".")

    old_function = '''    def demo_replace_target(self):

        print("OLD VERSION")

        return False
'''

    new_function = '''    def demo_replace_target(self):

        print("This function was replaced safely in memory.")

        return True
'''

    diff = engine.preview_function_replace(
        old_function_source=old_function,
        new_function_source=new_function,
        file_path="execution/function_replacer_test_target.py",
        function_name="demo_replace_target"
    )

    print("\n" + "=" * 60)
    print("DIFF PREVIEW")
    print("=" * 60)

    print(diff)