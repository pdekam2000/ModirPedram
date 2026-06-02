try:
    from execution.semantic_patch_engine import (
        SemanticPatchEngine,
    )
except ImportError:
    from semantic_patch_engine import SemanticPatchEngine


class RuntimePatchGeneratorAgent:

    """
    Runtime Patch Generator Agent V2

    Delegates to SemanticPatchEngine for safe
    incremental edits on old_source.
    """

    def __init__(self):

        self.semantic_engine = SemanticPatchEngine()

    def run(
        self,
        function_name,
        class_name,
        old_source,
        change_request
    ):

        result = self.semantic_engine.build_semantic_patch(
            old_source=old_source,
            change_request=change_request,
        )

        if not result.get("success"):

            return {
                "success": False,
                "status": result.get(
                    "status",
                    "FAILED_TO_GENERATE",
                ),
                "message": result.get(
                    "message",
                    (
                        "Patch generation failed safely. "
                        "No code was changed."
                    ),
                ),
                "patch_strategy": result.get(
                    "patch_strategy"
                ),
                "operations_applied": result.get(
                    "operations_applied",
                    [],
                ),
                "ast_valid_after_each_step": result.get(
                    "ast_valid_after_each_step",
                    False,
                ),
                "new_function_source": None,
            }

        return {
            "success": True,
            "status": "SUCCESS",
            "message": "Semantic patch generated safely.",
            "patch_strategy": result.get(
                "patch_strategy",
                SemanticPatchEngine.STRATEGY_SEMANTIC_INCREMENTAL_SAFE,
            ),
            "operations_applied": result.get(
                "operations_applied",
                [],
            ),
            "ast_valid_after_each_step": result.get(
                "ast_valid_after_each_step",
                True,
            ),
            "old_source_preserved": result.get(
                "old_source_preserved",
                True,
            ),
            "new_function_source": result.get(
                "new_function_source"
            ),
        }


if __name__ == "__main__":

    agent = RuntimePatchGeneratorAgent()

    result = agent.run(
        function_name="demo_replace_target",
        class_name="Demo",
        old_source="""
    def demo_replace_target(self):

        print("OLD")

        return False
""",
        change_request=(
            "Change print message to AI GENERATED PATCH"
        ),
    )

    print(result)
