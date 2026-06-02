from datetime import datetime


class PatchPlannerAgent:

    """
    Patch Planner Agent V1

    Purpose:
    - Decide patch strategy
    - Decide operation type
    - Estimate risk
    - Prepare execution order

    This is planning-only.
    No file modification occurs here.
    """

    def __init__(self, project_root="."):

        self.project_root = project_root

    # =====================================================
    # DETECT OPERATION
    # =====================================================

    def detect_operation(
        self,
        goal,
        context
    ):

        goal_lower = goal.lower()

        existing_functions = set(
            context.get("functions", [])
        )

        # ---------------------------------------------

        if "upgrade" in goal_lower:

            if (
                "retry"
                in goal_lower
                and
                "retry_generation"
                in existing_functions
            ):

                return {
                    "operation":
                        "REPLACE_FUNCTION",

                    "target_function":
                        "retry_generation",

                    "reason":
                        "Existing function upgrade detected"
                }

        # ---------------------------------------------

        if "add" in goal_lower:

            if (
                "retry"
                in goal_lower
                and
                "retry_generation"
                not in existing_functions
            ):

                return {
                    "operation":
                        "APPEND_FUNCTION",

                    "target_function":
                        "retry_generation",

                    "reason":
                        "Missing function detected"
                }

        # ---------------------------------------------

        return {
            "operation":
                "NO_PATCH",

            "target_function":
                "",

            "reason":
                "No valid operation detected"
        }

    # =====================================================
    # RISK ESTIMATION
    # =====================================================

    def estimate_risk(
        self,
        operation
    ):

        if operation == "REPLACE_FUNCTION":
            return "MEDIUM"

        if operation == "APPEND_FUNCTION":
            return "LOW"

        return "UNKNOWN"

    # =====================================================
    # BUILD EXECUTION PLAN
    # =====================================================

    def build_execution_plan(
        self,
        operation
    ):

        if operation == "REPLACE_FUNCTION":

            return [
                "Extract existing function",
                "Generate replacement",
                "Build diff preview",
                "Request approval",
                "Create backup",
                "Apply replace patch",
                "Run verifier",
            ]

        if operation == "APPEND_FUNCTION":

            return [
                "Generate append patch",
                "Preview patch",
                "Validate patch",
                "Request approval",
                "Create backup",
                "Apply append patch",
                "Run verifier",
            ]

        return [
            "No execution steps available"
        ]

    # =====================================================
    # PLAN
    # =====================================================

    def build_plan(
        self,
        goal,
        context,
        target_file
    ):

        operation_data = self.detect_operation(
            goal,
            context
        )

        operation = operation_data["operation"]

        risk = self.estimate_risk(
            operation
        )

        execution_steps = (
            self.build_execution_plan(
                operation
            )
        )

        return {
            "timestamp":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "goal":
                goal,

            "target_file":
                target_file,

            "operation":
                operation,

            "target_function":
                operation_data[
                    "target_function"
                ],

            "reason":
                operation_data[
                    "reason"
                ],

            "risk":
                risk,

            "approval_required":
                True,

            "backup_required":
                True,

            "execution_steps":
                execution_steps,

            "status":
                "PLAN_READY"
                if operation != "NO_PATCH"
                else "PLAN_BLOCKED"
        }

    # =====================================================
    # DISPLAY
    # =====================================================

    def print_plan(
        self,
        plan
    ):

        print("")
        print("=" * 60)
        print("PATCH EXECUTION PLAN")
        print("=" * 60)

        print("")
        print(
            f"Goal: "
            f"{plan['goal']}"
        )

        print(
            f"Target File: "
            f"{plan['target_file']}"
        )

        print(
            f"Operation: "
            f"{plan['operation']}"
        )

        print(
            f"Function: "
            f"{plan['target_function']}"
        )

        print(
            f"Risk: "
            f"{plan['risk']}"
        )

        print(
            f"Reason: "
            f"{plan['reason']}"
        )

        print("")
        print("Execution Steps:")

        print("")

        for index, step in enumerate(
            plan["execution_steps"],
            start=1
        ):

            print(
                f"{index}. {step}"
            )

        print("")
        print(
            f"Status: "
            f"{plan['status']}"
        )

        print("")

    # =====================================================
    # RUN
    # =====================================================

    def run(
        self,
        goal,
        context,
        target_file
    ):

        plan = self.build_plan(
            goal=goal,
            context=context,
            target_file=target_file
        )

        self.print_plan(
            plan
        )

        return plan


if __name__ == "__main__":

    context = {
        "functions": [
            "retry_generation",
            "timeout_wrapper"
        ]
    }

    agent = PatchPlannerAgent(".")

    agent.run(
        goal="upgrade retry mechanism",
        context=context,
        target_file=
        "providers/runway_video_provider.py"
    )