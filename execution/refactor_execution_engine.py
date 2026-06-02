from datetime import datetime

try:
    from execution.runtime_state_manager import RuntimeStateManager
except ImportError:
    from runtime_state_manager import RuntimeStateManager

try:
    from execution.action_executor_registry import ActionExecutorRegistry
except ImportError:
    from action_executor_registry import ActionExecutorRegistry

try:
    from execution.action_context_builder import ActionContextBuilder
except ImportError:
    from action_context_builder import ActionContextBuilder


class RefactorExecutionEngine:

    """
    Refactor Execution Engine V2

    Real Runtime Execution Enabled

    Connected:
    - EXTRACT_FUNCTION
    - APPLY_REPLACE_PATCH
    - RUN_VERIFIER

    Safety:
    - Approval gate still active
    - Rollback still safe-mode
    """

    def __init__(self, project_root="."):

        self.project_root = project_root

        self.execution_log = []

        self.state_manager = RuntimeStateManager(
            project_root
        )

        self.action_registry = ActionExecutorRegistry(
            project_root
        )

        self.context_builder = ActionContextBuilder(
            project_root
        )

    # =====================================================
    # LOGGING
    # =====================================================

    def log_step(
        self,
        step,
        action,
        status,
        message=""
    ):

        entry = {
            "timestamp":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "step":
                step,

            "action":
                action,

            "status":
                status,

            "message":
                message,
        }

        self.execution_log.append(entry)

    # =====================================================
    # EXECUTE STEP
    # =====================================================

    def execute_step(
        self,
        queue_item,
        runtime_state=None,
        patch_data=None
    ):

        step = queue_item["step"]

        action = queue_item["action"]

        print("")
        print(
            f"[STEP {step}] "
            f"{action}"
        )

        action_context = self.context_builder.build(
            queue_item=queue_item,
            runtime_state=runtime_state,
            patch_data=patch_data
        )

        if queue_item.get(
            "approval_granted"
        ) is True:

            action_context[
                "approval_granted"
            ] = True

        result = self.action_registry.execute(
            action=action,
            payload=action_context
        )

        self.log_step(
            step=step,
            action=action,
            status=result.get(
                "status",
                "UNKNOWN"
            ),
            message=result.get(
                "message",
                ""
            )
        )

        return {
            "success":
                result.get(
                    "success",
                    False
                ),

            "result":
                result,

            "action_context":
                action_context,
        }

    # =====================================================
    # ROLLBACK
    # =====================================================

    def trigger_rollback(
        self,
        rollback_strategy
    ):

        print("")
        print("=" * 60)
        print("ROLLBACK TRIGGERED")
        print("=" * 60)

        for item in rollback_strategy:

            print(
                f"- {item['rollback_action']}"
            )

    # =====================================================
    # EXECUTE PLAN
    # =====================================================

    def execute_plan(
        self,
        orchestration_plan,
        goal="runtime execution"
    ):

        state = self.state_manager.build_initial_state(
            goal=goal,
            orchestration_plan=orchestration_plan,
        )

        state = self.state_manager.mark_running(
            state
        )

        self.state_manager.save_state(state)

        queue = orchestration_plan["queue"]

        rollback_strategy = orchestration_plan[
            "rollback_strategy"
        ]

        print("")
        print("=" * 60)
        print("EXECUTION STARTED")
        print("=" * 60)

        for item in queue:

            step_result = self.execute_step(
                queue_item=item,
                runtime_state=state,
                patch_data=orchestration_plan.get(
                    "patch_data",
                    {}
                )
            )

            success = step_result.get(
                "success",
                False
            )

            latest_log = self.execution_log[-1]

            state = self.state_manager.update_step(
                state=state,
                step=latest_log["step"],
                action=latest_log["action"],
                status=latest_log["status"],
                message=latest_log["message"],
                action_context=step_result.get(
                    "action_context",
                    {}
                )
            )

            self.state_manager.save_state(state)

            if not success:

                if item["action"] != "REQUEST_APPROVAL":

                    self.trigger_rollback(
                        rollback_strategy
                    )

                print("")
                print("Execution stopped.")

                return {
                    "status":
                        "EXECUTION_STOPPED",

                    "session_id":
                        state["session_id"],

                    "execution_log":
                        self.execution_log,
                }

        state = self.state_manager.mark_complete(
            state
        )

        self.state_manager.save_state(state)

        print("")
        print("=" * 60)
        print("EXECUTION COMPLETE")
        print("=" * 60)

        return {
            "status":
                "EXECUTION_COMPLETE",

            "session_id":
                state["session_id"],

            "execution_log":
                self.execution_log,
        }

    # =====================================================
    # DISPLAY LOG
    # =====================================================

    def print_execution_log(self):

        print("")
        print("=" * 60)
        print("EXECUTION LOG")
        print("=" * 60)

        for entry in self.execution_log:

            print("")

            print(
                f"[{entry['status']}] "
                f"STEP {entry['step']} "
                f"- {entry['action']}"
            )

            print(
                f"Message: "
                f"{entry['message']}"
            )

    # =====================================================
    # RUN
    # =====================================================

    def run(
        self,
        orchestration_plan,
        goal="runtime execution"
    ):

        result = self.execute_plan(
            orchestration_plan=orchestration_plan,
            goal=goal,
        )

        self.print_execution_log()

        print("")
        print(
            f"Runtime Session: "
            f"{result.get('session_id')}"
        )

        return result


if __name__ == "__main__":

    orchestration_plan = {

        "patch_data": {

            "target_file":
                "execution/apply_replace_patch_test_target.py",

            "function_name":
                "demo_replace_target",

            "class_name":
                "Demo",

            "new_function_source":
'''
def demo_replace_target(self):

    print("FULL RUNTIME EXECUTION SUCCESS")

    return True
'''
        },

        "queue": [

            {
                "step": 1,
                "action": "EXTRACT_FUNCTION",
            },

            {
                "step": 2,
                "action": "APPLY_REPLACE_PATCH",
                "approval_granted": True,
            },

            {
                "step": 3,
                "action": "RUN_VERIFIER",
            },
        ],

        "rollback_strategy": [
            {
                "rollback_action":
                    "RESTORE_BACKUP",
            }
        ],
    }

    engine = RefactorExecutionEngine(".")

    engine.run(
        orchestration_plan
    )