from pathlib import Path
import inspect


try:
    from execution.function_extractor import FunctionExtractor
except ImportError:
    from function_extractor import FunctionExtractor

try:
    from execution.apply_replace_patch_engine import ApplyReplacePatchEngine
except ImportError:
    from apply_replace_patch_engine import ApplyReplacePatchEngine
    
try:
    from agents.verifier_agent import VerifierAgent
except ImportError:
    from verifier_agent import VerifierAgent


class ActionExecutorRegistry:

    """
    Action Executor Registry V2

    Real handlers connected:
    - EXTRACT_FUNCTION
    - APPLY_REPLACE_PATCH preview mode

    Safety:
    - REQUEST_APPROVAL still stops runtime.
    - APPLY_REPLACE_PATCH only applies if approval_granted=True.
    """

    def __init__(self, project_root="."):

        self.project_root = Path(project_root).resolve()

        self.handlers = {
            "EXTRACT_FUNCTION": self.handle_extract_function,
            "GENERATE_REPLACEMENT": self.handle_generate_replacement,
            "BUILD_DIFF": self.handle_build_diff,
            "REQUEST_APPROVAL": self.handle_request_approval,
            "CREATE_BACKUP": self.handle_create_backup,
            "APPLY_REPLACE_PATCH": self.handle_apply_replace_patch,
            "APPLY_APPEND_PATCH": self.handle_apply_append_patch,
            "RUN_VERIFIER": self.handle_run_verifier,
        }

    def execute(self, action, payload=None):

        if payload is None:
            payload = {}

        handler = self.handlers.get(action)

        if handler is None:
            return self.build_failure(
                action=action,
                status="UNKNOWN_ACTION",
                message="No handler registered for action.",
                data={}
            )

        try:
            return handler(payload)

        except Exception as error:
            return self.build_failure(
                action=action,
                status="FAILED",
                message=str(error),
                data={
                    "error_type": type(error).__name__,
                    "payload": payload,
                }
            )

    def build_success(self, action, message, data=None):

        return {
            "success": True,
            "status": "SUCCESS",
            "action": action,
            "message": message,
            "data": data or {},
        }

    def build_failure(self, action, status, message, data=None):

        return {
            "success": False,
            "status": status,
            "action": action,
            "message": message,
            "data": data or {},
        }

    def build_waiting_approval(self, action, message, data=None):

        return {
            "success": False,
            "status": "WAITING_APPROVAL",
            "action": action,
            "message": message,
            "data": data or {},
        }

    def resolve_target_path(self, payload):

        target_file = payload.get("target_file")

        if not target_file:
            patch_data = payload.get("patch_data", {})
            target_file = patch_data.get("target_file")

        if not target_file:
            return None

        target_path = Path(target_file)

        if not target_path.is_absolute():
            target_path = self.project_root / target_path

        return target_path

    def get_patch_data_value(self, payload, *keys):

        patch_data = payload.get("patch_data", {})

        for key in keys:
            value = payload.get(key)

            if value:
                return value

            value = patch_data.get(key)

            if value:
                return value

        return None

    def call_extractor_safely(
        self,
        extractor,
        target_path,
        target_function,
        class_name=None
    ):

        extract_method = getattr(extractor, "extract", None)

        if extract_method is None:
            raise AttributeError(
                "FunctionExtractor has no extract() method."
            )

        signature = inspect.signature(extract_method)
        parameters = signature.parameters

        kwargs = {}

        if "target_file" in parameters:
            kwargs["target_file"] = str(target_path)

        if "file_path" in parameters:
            kwargs["file_path"] = str(target_path)

        if "path" in parameters:
            kwargs["path"] = str(target_path)

        if "target_function" in parameters:
            kwargs["target_function"] = target_function

        if "function_name" in parameters:
            kwargs["function_name"] = target_function

        if "class_name" in parameters:
            kwargs["class_name"] = class_name

        if kwargs:
            return extract_method(**kwargs)

        return extract_method(
            str(target_path),
            target_function
        )

    def handle_extract_function(self, payload):

        target_path = self.resolve_target_path(payload)

        target_function = self.get_patch_data_value(
            payload,
            "target_function",
            "function_name"
        )

        class_name = self.get_patch_data_value(
            payload,
            "class_name"
        )

        if target_path is None:
            return self.build_failure(
                action="EXTRACT_FUNCTION",
                status="MISSING_TARGET_FILE",
                message="target_file is required for EXTRACT_FUNCTION.",
                data=payload
            )

        if not target_path.exists():
            return self.build_failure(
                action="EXTRACT_FUNCTION",
                status="TARGET_FILE_NOT_FOUND",
                message=f"Target file not found: {target_path}",
                data={
                    "target_file": str(target_path),
                    "payload": payload,
                }
            )

        if not target_function:
            return self.build_failure(
                action="EXTRACT_FUNCTION",
                status="MISSING_TARGET_FUNCTION",
                message="target_function is required for EXTRACT_FUNCTION.",
                data=payload
            )

        extractor = FunctionExtractor()

        extracted_data = self.call_extractor_safely(
            extractor=extractor,
            target_path=target_path,
            target_function=target_function,
            class_name=class_name
        )

        return self.build_success(
            action="EXTRACT_FUNCTION",
            message="Function extracted successfully using real FunctionExtractor.",
            data={
                "target_file": str(target_path),
                "target_function": target_function,
                "class_name": class_name,
                "extracted": extracted_data,
                "payload": payload,
            }
        )

    def handle_generate_replacement(self, payload):

        return self.build_success(
            action="GENERATE_REPLACEMENT",
            message="Replacement generation step completed. Still simulated.",
            data=payload
        )

    def handle_build_diff(self, payload):

        return self.build_success(
            action="BUILD_DIFF",
            message="Diff build step completed. Still simulated.",
            data=payload
        )

    def handle_request_approval(self, payload):

        return self.build_waiting_approval(
            action="REQUEST_APPROVAL",
            message="User approval required before applying patch.",
            data=payload
        )

    def handle_create_backup(self, payload):

        return self.build_success(
            action="CREATE_BACKUP",
            message="Backup step completed. Still simulated.",
            data=payload
        )

    def handle_apply_replace_patch(self, payload):

        target_path = self.resolve_target_path(payload)

        function_name = self.get_patch_data_value(
            payload,
            "target_function",
            "function_name"
        )

        class_name = self.get_patch_data_value(
            payload,
            "class_name"
        )

        new_function_source = self.get_patch_data_value(
            payload,
            "new_function_source",
            "code"
        )

        approval_granted = payload.get(
            "approval_granted",
            False
        )

        if target_path is None:
            return self.build_failure(
                action="APPLY_REPLACE_PATCH",
                status="MISSING_TARGET_FILE",
                message="target_file is required for APPLY_REPLACE_PATCH.",
                data=payload
            )

        if not function_name:
            return self.build_failure(
                action="APPLY_REPLACE_PATCH",
                status="MISSING_FUNCTION_NAME",
                message="function_name is required for APPLY_REPLACE_PATCH.",
                data=payload
            )

        if not new_function_source:
            return self.build_failure(
                action="APPLY_REPLACE_PATCH",
                status="MISSING_NEW_FUNCTION_SOURCE",
                message="new_function_source or code is required.",
                data=payload
            )

        engine = ApplyReplacePatchEngine(
            project_root=str(self.project_root)
        )

        result = engine.apply_replace_patch(
            file_path=str(target_path),
            function_name=function_name,
            class_name=class_name,
            new_function_source=new_function_source,
            approve=approval_granted
        )

        status = result.get("status")

        if status == "WAITING_APPROVAL":
            return self.build_waiting_approval(
                action="APPLY_REPLACE_PATCH",
                message="Replace patch preview built. Waiting for approval.",
                data=result
            )

        if status == "PATCH_APPLIED":
            return self.build_success(
                action="APPLY_REPLACE_PATCH",
                message="Replace patch applied successfully.",
                data=result
            )

        return self.build_failure(
            action="APPLY_REPLACE_PATCH",
            status=status or "APPLY_REPLACE_PATCH_FAILED",
            message=result.get(
                "message",
                "Apply replace patch failed."
            ),
            data=result
        )

    def handle_apply_append_patch(self, payload):

        return self.build_success(
            action="APPLY_APPEND_PATCH",
            message="Append patch apply step completed. Still simulated.",
            data=payload
        )

    def handle_run_verifier(self, payload):

        verifier = VerifierAgent(
            project_root=str(self.project_root)
        )

        output = verifier.save_report()

        return self.build_success(
            action="RUN_VERIFIER",
            message="VerifierAgent executed successfully.",
            data={
                "verification_report": output,
                "payload": payload,
            }
        )

if __name__ == "__main__":

    registry = ActionExecutorRegistry(".")

    test_payload = {
        "target_file": "execution/apply_replace_patch_test_target.py",
        "function_name": "demo_replace_target",
        "class_name": "Demo",
        "new_function_source": """
def demo_replace_target(self):

    print("UPDATED FROM ACTION REGISTRY")

    return True
""",
        "approval_granted": False,
    }

    result = registry.execute(
        action="APPLY_REPLACE_PATCH",
        payload=test_payload
    )

    print("")
    print("=" * 60)
    print("ACTION EXECUTOR REGISTRY V2 APPLY TEST")
    print("=" * 60)
    print(result)