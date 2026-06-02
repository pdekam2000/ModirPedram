from pathlib import Path
from datetime import datetime


class ActionContextBuilder:

    """
    Action Context Builder V1

    UI-ready context builder.

    Purpose:
    - Convert queue items into executable payloads
    - Inject runtime/session metadata
    - Inject patch data
    - Keep execution engine clean
    - Prepare real action handlers for V2
    """

    def __init__(self, project_root="."):

        self.project_root = Path(project_root).resolve()

    def build_base_context(
        self,
        queue_item,
        runtime_state=None,
        patch_data=None
    ):

        if runtime_state is None:
            runtime_state = {}

        if patch_data is None:
            patch_data = {}

        return {
            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "project_root": str(self.project_root),
            "session_id": runtime_state.get(
                "session_id"
            ),
            "runtime_status": runtime_state.get(
                "status"
            ),
            "step": queue_item.get(
                "step"
            ),
            "action": queue_item.get(
                "action"
            ),
            "target_file": queue_item.get(
                "target_file"
            ),
            "target_function": queue_item.get(
                "target_function"
            ),
            "class_name": queue_item.get(
                "class_name"
            ),
            "patch_data": patch_data,
            "ui": {
                "display_action": queue_item.get(
                    "action"
                ),
                "progress_step": queue_item.get(
                    "step"
                ),
                "requires_user_action": False,
            }
        }

    def enrich_for_action(
        self,
        action_context
    ):

        action = action_context.get(
            "action"
        )

        if action == "REQUEST_APPROVAL":

            action_context["ui"][
                "requires_user_action"
            ] = True

            action_context["approval"] = {
                "required": True,
                "granted": False,
                "message":
                    "User approval required before apply."
            }

        if action in [
            "APPLY_REPLACE_PATCH",
            "APPLY_APPEND_PATCH"
        ]:

            action_context["safety"] = {
                "backup_required": True,
                "approval_required": True,
            }

        if action == "RUN_VERIFIER":

            action_context["verification"] = {
                "required": True,
                "mode": "standard"
            }

        return action_context

    def build(
        self,
        queue_item,
        runtime_state=None,
        patch_data=None
    ):

        context = self.build_base_context(
            queue_item=queue_item,
            runtime_state=runtime_state,
            patch_data=patch_data
        )

        context = self.enrich_for_action(
            context
        )

        return context


if __name__ == "__main__":

    builder = ActionContextBuilder(".")

    runtime_state = {
        "session_id": "runtime_test_123",
        "status": "RUNNING"
    }

    patch_data = {
        "operation": "REPLACE_FUNCTION",
        "target_file": "providers/runway_video_provider.py",
        "function_name": "retry_generation",
        "code": "def retry_generation(...): pass"
    }

    queue_item = {
        "step": 4,
        "action": "REQUEST_APPROVAL",
        "target_file": "providers/runway_video_provider.py",
        "target_function": "retry_generation",
    }

    context = builder.build(
        queue_item=queue_item,
        runtime_state=runtime_state,
        patch_data=patch_data
    )

    print("\n" + "=" * 60)
    print("ACTION CONTEXT BUILDER TEST")
    print("=" * 60)

    print("")
    print(context)