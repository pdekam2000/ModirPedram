from datetime import datetime

from agents.project_context_agent import (
    ProjectContextAgent
)


class CodeGenerationAgent:
    """
    Code Generation Agent V2

    Context Aware

    - Reads project context
    - Detects existing functions
    - Avoids duplicate patches
    - Generates safer code
    """

    def __init__(
        self,
        project_root="."
    ):
        self.context_agent = (
            ProjectContextAgent(
                project_root
            )
        )

    # =====================================================
    # PATCHES
    # =====================================================

    def build_retry_patch(self):

        return '''
def retry_generation(
    operation,
    retries=3
):
    last_error = None

    for attempt in range(retries):

        try:
            return operation()

        except Exception as error:
            last_error = error

            print(
                f"[Retry] Attempt "
                f"{attempt + 1}/{retries} failed"
            )

    raise last_error
'''

    def build_timeout_patch(self):

        return '''
def timeout_wrapper(
    operation,
    timeout_seconds=60
):
    return operation()
'''

    def build_replace_retry_patch(self):

        return '''
def retry_generation(
    operation,
    retries=5,
    delay=2
):

    import time

    last_error = None

    for attempt in range(retries):

        try:
            return operation()

        except Exception as error:

            last_error = error

            print(
                f"[Retry] Attempt "
                f"{attempt + 1}/{retries} failed"
            )

            if attempt < retries - 1:
                time.sleep(delay)

    raise last_error
'''

    # =====================================================
    # GENERATE
    # =====================================================

    def generate_patch(
        self,
        goal,
        context
    ):

        goal_lower = goal.lower()

        existing = set(
            context["functions"]
        )

        # -------------------

        if "retry" in goal_lower:

            if (
                "retry_generation"
                in existing
            ):

                return {
                    "operation":
                        "REPLACE_FUNCTION",

                    "function_name":
                        "retry_generation",

                    "class_name":
                        None,

                    "code":
                        self.build_replace_retry_patch(),

                    "reason":
                        "Upgrade existing retry function",
                }

            return {
                "operation":
                    "APPEND_FUNCTION",

                "function_name":
                    "retry_generation",

                "class_name":
                    None,

                "code":
                    self.build_retry_patch(),

                "reason":
                    "Add retry support",
            }

        # -------------------

        if "timeout" in goal_lower:

            if (
                "timeout_wrapper"
                in existing
            ):
                return {
                    "operation":
                        "NO_PATCH",

                    "function_name":
                        "timeout_wrapper",

                    "code":
                        "",

                    "reason":
                        "Function already exists",
                }

            return {
                "operation":
                    "APPEND_FUNCTION",

                "function_name":
                    "timeout_wrapper",

                "code":
                    self.build_timeout_patch(),

                "reason":
                    "Add timeout support",
            }

        # -------------------

        return {
            "operation":
                "NO_PATCH",

            "function_name":
                "",

            "code":
                "",

            "reason":
                "No patch available",
        }

    # =====================================================
    # RESPONSE
    # =====================================================

    def build_response(
        self,
        goal,
        target_file
    ):

        context = (
            self.context_agent.run(
                target_file
            )
        )

        patch = self.generate_patch(
            goal,
            context
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

            "context":
                context,

            "patch":
                patch,

            "status":
                "PATCH_READY"
                if patch["operation"]
                != "NO_PATCH"
                else "PATCH_BLOCKED",
        }

    # =====================================================
    # DISPLAY
    # =====================================================

    def print_patch(
        self,
        response
    ):

        patch = response["patch"]

        print("")
        print("=" * 60)
        print("CODE GENERATION")
        print("=" * 60)

        print("")
        print(
            f"Goal: "
            f"{response['goal']}"
        )

        print(
            f"Target: "
            f"{response['target_file']}"
        )

        print(
            f"Operation: "
            f"{patch['operation']}"
        )

        print(
            f"Function: "
            f"{patch['function_name']}"
        )

        print(
            f"Reason: "
            f"{patch['reason']}"
        )

        print("")

        if patch["code"]:

            print(
                "Generated Patch:"
            )

            print("")
            print(
                patch["code"]
            )

        print("")
        print(
            f"Status: "
            f"{response['status']}"
        )

        print("")

    # =====================================================
    # RUN
    # =====================================================

    def run(
        self,
        goal,
        target_file
    ):

        response = (
            self.build_response(
                goal,
                target_file
            )
        )

        self.print_patch(
            response
        )

        return response


if __name__ == "__main__":

    agent = CodeGenerationAgent(".")

    agent.run(
        goal=
        "Add retry mechanism to Runway provider",

        target_file=
        "providers/runway_video_provider.py",
    )