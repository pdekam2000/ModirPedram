from execution.approval_engine import ApprovalEngine
from execution.patch_validator import PatchValidator
from execution.safe_code_editor import SafeCodeEditor


class ApplyPatchEngine:
    """
    Apply Patch Engine V1

    Flow:

    Approval
      ↓
    Validation
      ↓
    Backup
      ↓
    Apply
      ↓
    Result

    Allowed Operations:
    - APPEND_FUNCTION
    - CREATE_FILE

    Blocked:
    - DELETE
    - REWRITE
    - REMOVE
    """

    def __init__(self, project_root="."):

        self.approval = ApprovalEngine(
            project_root
        )

        self.validator = PatchValidator(
            project_root
        )

        self.editor = SafeCodeEditor(
            project_root
        )

    # =====================================================
    # APPEND PATCH
    # =====================================================

    def append_patch(
        self,
        approval_text: str,
        goal: str,
        target_file: str,
        patch_code: str
    ):

        approved = (
            self.approval.require_approval(
                approval_text=approval_text,
                goal=goal,
                target_file=target_file,
                operation="APPEND_FUNCTION"
            )
        )

        if not approved:

            return {
                "success": False,
                "reason": "Approval denied"
            }

        validation = self.validator.validate(
            target_file=target_file,
            patch_code=patch_code
        )

        if not validation["valid"]:

            return {
                "success": False,
                "reason": validation["errors"]
            }

        self.editor.append_text(
            relative_path=target_file,
            text="\n\n" + patch_code
        )

        return {
            "success": True,
            "operation": "APPEND_FUNCTION",
            "target": target_file
        }

    # =====================================================
    # CREATE FILE
    # =====================================================

    def create_file(
        self,
        approval_text: str,
        goal: str,
        target_file: str,
        content: str
    ):

        approved = (
            self.approval.require_approval(
                approval_text=approval_text,
                goal=goal,
                target_file=target_file,
                operation="CREATE_FILE"
            )
        )

        if not approved:

            return {
                "success": False,
                "reason": "Approval denied"
            }

        self.editor.create_file(
            relative_path=target_file,
            content=content,
            overwrite=False
        )

        return {
            "success": True,
            "operation": "CREATE_FILE",
            "target": target_file
        }


if __name__ == "__main__":

    engine = ApplyPatchEngine(".")

    sample_patch = """
def retry_generation(
    operation,
    retries=3
):
    pass
"""

    result = engine.append_patch(
        approval_text="approve",

        goal=
        "Add retry mechanism",

        target_file=
        "providers/runway_video_provider.py",

        patch_code=
        sample_patch
    )

    print("")
    print("=" * 60)
    print("APPLY PATCH ENGINE")
    print("=" * 60)
    print("")
    print(result)
    print("")