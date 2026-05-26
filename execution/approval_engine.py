from datetime import datetime
from pathlib import Path


class ApprovalEngine:
    """
    Approval Engine V1

    Purpose:
    - Block edits unless approval is explicit
    - Keep approval logs
    - Used before SafeCodeEditor applies patches
    """

    def __init__(self, project_root="."):
        self.project_root = Path(project_root).resolve()
        self.brain_dir = self.project_root / "project_brain"
        self.approval_log = self.brain_dir / "approval_log.md"

        self.brain_dir.mkdir(parents=True, exist_ok=True)

    def is_approved(self, approval_text: str) -> bool:
        if not approval_text:
            return False

        allowed = {
            "approve",
            "approved",
            "yes",
            "ok",
            "apply",
            "اجازه",
            "تایید",
            "تأیید",
        }

        return approval_text.strip().lower() in allowed

    def require_approval(
        self,
        approval_text: str,
        goal: str,
        target_file: str,
        operation: str
    ) -> bool:

        approved = self.is_approved(approval_text)

        with self.approval_log.open("a", encoding="utf-8") as file:
            file.write("\n\n")
            file.write("## Approval Check\n")
            file.write(f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            file.write(f"- Goal: {goal}\n")
            file.write(f"- Target: {target_file}\n")
            file.write(f"- Operation: {operation}\n")
            file.write(f"- Approval Text: {approval_text}\n")
            file.write(f"- Approved: {approved}\n")

        return approved


if __name__ == "__main__":
    engine = ApprovalEngine(".")

    result = engine.require_approval(
        approval_text="approve",
        goal="Test approval system",
        target_file="test.py",
        operation="APPEND"
    )

    print("")
    print("=" * 60)
    print("MODIRAGENT APPROVAL ENGINE")
    print("=" * 60)
    print("")
    print(f"Approved: {result}")
    print("No files were modified.")
    print("")