from execution.action_executor_registry import (
    ActionExecutorRegistry
)

registry = ActionExecutorRegistry(".")

result = registry.execute(
    action="APPLY_REPLACE_PATCH",
    payload={
        "target_file":
            "execution/apply_replace_patch_test_target.py",

        "function_name":
            "demo_replace_target",

        "class_name":
            "Demo",

        "new_function_source":
'''
def demo_replace_target(self):

    print("APPLIED BY REAL ACTION HANDLER")

    return True
''',

        "approval_granted":
            True,
    }
)

print("")
print("=" * 60)
print("REAL APPLY TEST")
print("=" * 60)
print(result)