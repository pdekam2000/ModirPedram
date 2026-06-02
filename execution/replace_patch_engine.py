from pathlib import Path

from execution.function_extractor import FunctionExtractor
from execution.function_replacer import FunctionReplacer
from execution.diff_preview_engine import DiffPreviewEngine


class ReplacePatchEngine:

    """
    Builds a safe replace-function patch preview.

    This engine does NOT write to disk.
    It only:
    - extracts old function
    - validates replacement function
    - builds updated source in memory
    - creates diff preview
    """

    def __init__(self, project_root="."):

        self.project_root = Path(project_root).resolve()
        self.extractor = FunctionExtractor(project_root)
        self.replacer = FunctionReplacer(project_root)
        self.diff_engine = DiffPreviewEngine(project_root)

    def build_replace_patch(
        self,
        file_path,
        function_name,
        new_function_source,
        class_name=None,
        patch_metadata=None
    ):

        extracted = self.extractor.extract(
            file_path=file_path,
            function_name=function_name,
            class_name=class_name
        )

        replacement = self.replacer.replace_function(
            file_path=file_path,
            function_name=function_name,
            class_name=class_name,
            new_function_source=new_function_source
        )

        diff_preview = self.diff_engine.preview_function_replace(
            old_function_source=replacement["old_source"],
            new_function_source=replacement["new_source"],
            file_path=file_path,
            function_name=function_name
        )

        patch = {
            "patch_type": "REPLACE_FUNCTION",
            "file_path": replacement["file_path"],
            "function_name": function_name,
            "class_name": class_name,
            "start_line": extracted["start_line"],
            "end_line": extracted["end_line"],
            "old_source": replacement["old_source"],
            "new_source": replacement["new_source"],
            "updated_source": replacement["updated_source"],
            "diff_preview": diff_preview,
            "status": "PREVIEW_READY",
        }

        if patch_metadata:
            patch_strategy = patch_metadata.get(
                "patch_strategy"
            )

            if (
                patch_strategy
                == "SEMANTIC_INCREMENTAL_SAFE"
            ):
                patch["patch_type"] = (
                    "SEMANTIC_INCREMENTAL"
                )

            patch["patch_strategy"] = patch_strategy
            patch["operations_applied"] = (
                patch_metadata.get(
                    "operations_applied",
                    [],
                )
            )
            patch[
                "ast_valid_after_each_step"
            ] = patch_metadata.get(
                "ast_valid_after_each_step",
                False,
            )

        return patch


if __name__ == "__main__":

    engine = ReplacePatchEngine(".")

    test_file = "execution/replace_patch_engine_test_target.py"

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

    print("REPLACED THROUGH REPLACE PATCH ENGINE")

    return True
'''

    patch = engine.build_replace_patch(
        file_path=test_file,
        function_name="demo_replace_target",
        class_name="Demo",
        new_function_source=new_function
    )

    print("\n" + "=" * 60)
    print("REPLACE PATCH PREVIEW READY")
    print("=" * 60)

    print("\nPatch Type:", patch["patch_type"])
    print("Status:", patch["status"])
    print("File:", patch["file_path"])
    print("Function:", patch["function_name"])
    print("Lines:", patch["start_line"], "->", patch["end_line"])

    print("\n" + "=" * 60)
    print("DIFF PREVIEW")
    print("=" * 60)

    print(patch["diff_preview"])