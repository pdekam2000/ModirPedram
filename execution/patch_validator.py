from pathlib import Path
import ast


class PatchValidator:
    """
    Patch Validator V1

    Purpose:
    - Validate generated patches
    - Prevent dangerous apply operations
    - Run before SafeCodeEditor

    Checks:
    - Target file exists
    - Patch syntax valid
    - Duplicate function names
    """

    def __init__(self, project_root="."):
        self.project_root = Path(project_root).resolve()

    # =====================================================
    # HELPERS
    # =====================================================

    def resolve_path(
        self,
        relative_path: str
    ) -> Path:

        return (
            self.project_root
            / relative_path
        ).resolve()

    # =====================================================
    # FILE EXISTS
    # =====================================================

    def file_exists(
        self,
        relative_path: str
    ) -> bool:

        return self.resolve_path(
            relative_path
        ).exists()

    # =====================================================
    # PATCH SYNTAX
    # =====================================================

    def patch_has_valid_syntax(
        self,
        patch_code: str
    ) -> bool:

        try:
            ast.parse(patch_code)
            return True

        except Exception:
            return False

    # =====================================================
    # FUNCTION NAME
    # =====================================================

    def extract_function_name(
        self,
        patch_code: str
    ):

        try:
            tree = ast.parse(
                patch_code
            )

            for node in tree.body:

                if isinstance(
                    node,
                    ast.FunctionDef
                ):
                    return node.name

        except Exception:
            return None

        return None

    # =====================================================
    # DUPLICATE CHECK
    # =====================================================

    def function_already_exists(
        self,
        relative_path: str,
        function_name: str
    ) -> bool:

        if not function_name:
            return False

        file_path = self.resolve_path(
            relative_path
        )

        content = file_path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        return (
            f"def {function_name}("
            in content
        )

    # =====================================================
    # MAIN VALIDATION
    # =====================================================

    def validate(
        self,
        target_file: str,
        patch_code: str
    ):

        result = {
            "valid": True,
            "errors": [],
        }

        # -------------------

        if not self.file_exists(
            target_file
        ):
            result["valid"] = False

            result["errors"].append(
                "Target file does not exist"
            )

            return result

        # -------------------

        if not self.patch_has_valid_syntax(
            patch_code
        ):
            result["valid"] = False

            result["errors"].append(
                "Patch syntax invalid"
            )

            return result

        # -------------------

        function_name = (
            self.extract_function_name(
                patch_code
            )
        )

        if self.function_already_exists(
            target_file,
            function_name
        ):
            result["valid"] = False

            result["errors"].append(
                f"Function already exists: "
                f"{function_name}"
            )

        return result


if __name__ == "__main__":

    validator = PatchValidator(
        "."
    )

    sample_patch = """
def retry_generation(
    operation,
    retries=3
):
    pass
"""

    result = validator.validate(
        target_file=
        "providers/runway_video_provider.py",

        patch_code=
        sample_patch,
    )

    print("")
    print("=" * 60)
    print("PATCH VALIDATOR")
    print("=" * 60)
    print("")
    print(result)
    print("")