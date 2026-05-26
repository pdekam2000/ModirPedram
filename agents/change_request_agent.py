from datetime import datetime


class ChangeRequestAgent:
    """
    Change Request Agent V1

    Purpose:
    - Convert user goal into executable change request
    - Standardize modifications
    - Prepare SafeCodeEditor actions
    - No file modifications
    """

    def __init__(self):
        pass

    # =====================================================
    # DETECT OPERATION
    # =====================================================

    def detect_operation(self, goal: str) -> str:

        lower = goal.lower()

        if "add" in lower:
            return "APPEND"

        if "create" in lower:
            return "CREATE_FILE"

        if "replace" in lower:
            return "REPLACE"

        if "update" in lower:
            return "UPDATE"

        if "fix" in lower:
            return "PATCH"

        if "improve" in lower:
            return "UPGRADE"

        return "ANALYZE"

    # =====================================================
    # BUILD REQUEST
    # =====================================================

    def build_request(
        self,
        goal: str,
        core_files: list,
        impact_files: list
    ) -> dict:

        operation = self.detect_operation(
            goal
        )

        return {
            "timestamp":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "goal":
                goal,

            "operation":
                operation,

            "core_files":
                core_files,

            "impact_files":
                impact_files,

            "approval_required":
                True,

            "backup_required":
                True,

            "status":
                "WAITING_FOR_APPROVAL",
        }

    # =====================================================
    # DISPLAY
    # =====================================================

    def print_request(
        self,
        request: dict
    ):

        print("")
        print("=" * 60)
        print("CHANGE REQUEST")
        print("=" * 60)

        print("")
        print(
            f"Goal: {request['goal']}"
        )

        print(
            f"Operation: {request['operation']}"
        )

        print("")

        print("Core Files:")

        for file in request["core_files"]:
            print(f" - {file}")

        print("")
        print("Impact Files:")

        for file in request["impact_files"]:
            print(f" - {file}")

        print("")

        print(
            f"Approval Required: "
            f"{request['approval_required']}"
        )

        print(
            f"Backup Required: "
            f"{request['backup_required']}"
        )

        print(
            f"Status: "
            f"{request['status']}"
        )

        print("")

    # =====================================================
    # RUN
    # =====================================================

    def run(
        self,
        goal: str,
        core_files: list,
        impact_files: list
    ) -> dict:

        request = self.build_request(
            goal,
            core_files,
            impact_files
        )

        self.print_request(
            request
        )

        return request


if __name__ == "__main__":

    agent = ChangeRequestAgent()

    agent.run(
        goal="Improve Runway Retry System",

        core_files=[
            "providers/runway_video_provider.py"
        ],

        impact_files=[
            "core/video_provider_router.py",
            "engines/video_generation_engine.py",
        ],
    )