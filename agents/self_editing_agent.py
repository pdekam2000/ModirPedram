import argparse
from agents.refactor_orchestrator_agent import RefactorOrchestratorAgent
from agents.project_upgrade_agent import ProjectUpgradeAgent
from agents.change_request_agent import ChangeRequestAgent
from agents.code_generation_agent import CodeGenerationAgent
from agents.verifier_agent import VerifierAgent
from agents.patch_planner_agent import PatchPlannerAgent
from core.dependency_graph_engine import DependencyGraphEngine
from core.upgrade_planner_engine import UpgradePlannerEngine
from execution.replace_patch_engine import ReplacePatchEngine
from execution.apply_replace_patch_engine import ApplyReplacePatchEngine
from execution.patch_preview_engine import PatchPreviewEngine
from execution.patch_validator import PatchValidator
from execution.apply_patch_engine import ApplyPatchEngine
from execution.refactor_execution_engine import RefactorExecutionEngine
from execution.queue_payload_enricher import QueuePayloadEnricher
class SelfEditingAgent:
    """
    Self Editing Agent V5

    CLI supported:
    --goal
    --target
    --file
    --path
    --approve

    Default:
    Preview only.

    Apply:
    Only with --approve.
    """

    def __init__(self, project_root="."):
        self.project_root = project_root

        self.upgrade_agent = ProjectUpgradeAgent(project_root)
        self.graph_engine = DependencyGraphEngine(project_root)
        self.planner = UpgradePlannerEngine(project_root)
        self.change_request_agent = ChangeRequestAgent()
        self.code_generation_agent = CodeGenerationAgent()
        self.patch_planner_agent = PatchPlannerAgent(project_root)
        self.refactor_orchestrator = RefactorOrchestratorAgent(project_root)
        
        self.refactor_execution_engine = RefactorExecutionEngine(project_root)
        self.queue_payload_enricher = QueuePayloadEnricher()
        self.preview_engine = PatchPreviewEngine(project_root)
        self.validator = PatchValidator(project_root)
        self.apply_engine = ApplyPatchEngine(project_root)
        
        self.replace_engine = ReplacePatchEngine(project_root)
        self.apply_replace_engine = ( ApplyReplacePatchEngine(project_root))
        self.verifier = VerifierAgent(project_root)

    def analyze_request(self, goal, target_path=""):
        print("\n" + "=" * 70)
        print("STEP 1 - PROJECT ANALYSIS")
        print("=" * 70)

        self.upgrade_agent.run(
            user_goal=goal,
            target_path=target_path
        )

    def build_graph(self, target_module):
        print("\n" + "=" * 70)
        print("STEP 2 - DEPENDENCY GRAPH")
        print("=" * 70)

        self.graph_engine.run(target_module)

    def build_plan(self, goal, core_files, impact_files):
        print("\n" + "=" * 70)
        print("STEP 3 - EXECUTION PLAN")
        print("=" * 70)

        self.planner.run(
            goal=goal,
            core_files=core_files,
            impact_files=impact_files
        )

    def build_change_request(self, goal, core_files, impact_files):
        print("\n" + "=" * 70)
        print("STEP 4 - CHANGE REQUEST")
        print("=" * 70)

        return self.change_request_agent.run(
            goal=goal,
            core_files=core_files,
            impact_files=impact_files
        )

    def generate_code(self, goal, target_file):
        print("\n" + "=" * 70)
        print("STEP 5 - CODE GENERATION")
        print("=" * 70)

        return self.code_generation_agent.run(
            goal=goal,
            target_file=target_file
        )
    def build_patch_plan(self, goal, context, target_file):
        print("\n" + "=" * 70)
        print("STEP 5.5 - PATCH PLANNER")
        print("=" * 70)

        return self.patch_planner_agent.run(
            goal=goal,
            context=context,
            target_file=target_file
        )
    def build_refactor_orchestration(self, patch_plan):
        print("\n" + "=" * 70)
        print("STEP 5.6 - REFACTOR ORCHESTRATOR")
        print("=" * 70)

        return self.refactor_orchestrator.run(
            refactor_plan=patch_plan
        )
    def enrich_orchestration_plan(
        self,
        orchestration_plan,
        patch_data
    ):

        print("\n" + "=" * 70)
        print("STEP 5.65 - QUEUE PAYLOAD ENRICHMENT")
        print("=" * 70)

        return self.queue_payload_enricher.enrich_plan(
            orchestration_plan=orchestration_plan,
            patch_data=patch_data
        )
    def simulate_refactor_execution(self, orchestration_plan):
        print("\n" + "=" * 70)
        print("STEP 5.7 - REFACTOR EXECUTION ENGINE")
        print("=" * 70)

        return self.refactor_execution_engine.run(
            orchestration_plan
        )
    def preview_patch(self, target_file, patch_code):
        print("\n" + "=" * 70)
        print("STEP 6 - PATCH PREVIEW")
        print("=" * 70)

        preview = self.preview_engine.preview_append(
            relative_path=target_file,
            patch_text=patch_code
        )

        output = self.preview_engine.save_preview(preview)

        print("")
        print(f"Patch preview saved to: {output}")
        print("")

        return output

    def validate_patch(self, target_file, patch_code):
        print("\n" + "=" * 70)
        print("STEP 7 - PATCH VALIDATION")
        print("=" * 70)

        result = self.validator.validate(
            target_file=target_file,
            patch_code=patch_code
        )

        print("")
        print(result)
        print("")

        return result

    def apply_patch(self, approval_text, goal, target_file, patch_code):
        print("\n" + "=" * 70)
        print("STEP 8 - APPLY PATCH")
        print("=" * 70)

        result = self.apply_engine.append_patch(
            approval_text=approval_text,
            goal=goal,
            target_file=target_file,
            patch_code=patch_code
        )

        print("")
        print(result)
        print("")

        return result

    def run_verifier(self):
        print("\n" + "=" * 70)
        print("STEP 9 - VERIFIER")
        print("=" * 70)

        self.verifier.run()

    def run(
        self,
        goal,
        target_module,
        core_files,
        impact_files,
        target_path="",
        approve=False
    ):
        print("\n" + "=" * 70)
        print("MODIRAGENT SELF EDITING AGENT V5")
        print("=" * 70)

        target_file = core_files[0]

        self.analyze_request(goal, target_path)
        self.build_graph(target_module)
        self.build_plan(goal, core_files, impact_files)

        change_request = self.build_change_request(
            goal,
            core_files,
            impact_files
        )

        code_patch = self.generate_code(
            goal,
            target_file
        )
        
        patch_plan = self.build_patch_plan(
            goal=goal,
            context=code_patch.get("context", {}),
            target_file=target_file
        )
        refactor_orchestration = (
            self.build_refactor_orchestration(
                patch_plan
            )
        )
        refactor_orchestration = (
            self.enrich_orchestration_plan(
                orchestration_plan=refactor_orchestration,
                patch_data=code_patch
            )
        )
        execution_simulation = (
            self.simulate_refactor_execution(
                refactor_orchestration
            )
        )

        patch = code_patch.get("patch", {})
        patch_code = patch.get("code", "")
        patch_operation = patch.get("operation", "NO_PATCH")

        supported_operations = [
            "APPEND_FUNCTION",
            "REPLACE_FUNCTION"
        ]

        if patch_operation not in supported_operations:

            print("\n" + "=" * 70)
            print("PATCH BLOCKED")
            print("=" * 70)
            print("")
            print(
                f"Unsupported patch operation: "
                f"{patch_operation}"
            )
            print("No files were modified.")
            print("")

            return

        if not patch_code.strip():
            print("\n" + "=" * 70)
            print("PATCH BLOCKED")
            print("=" * 70)
            print("")
            print("Patch code is empty.")
            print("No files were modified.")
            print("")
            return
        if patch_operation == "REPLACE_FUNCTION":

            function_name = patch.get(
                "function_name"
            )

            class_name = patch.get(
                "class_name"
            )

            replace_preview = (
                self.replace_engine
                .build_replace_patch(
                    file_path=target_file,
                    function_name=function_name,
                    class_name=class_name,
                    new_function_source=patch_code
                )
            )

            print("\n" + "=" * 70)
            print("STEP 6 - REPLACE PATCH PREVIEW")
            print("=" * 70)

            print("")
            print(
                replace_preview["diff_preview"]
            )
            print("")

            if not approve:

                print("\n" + "=" * 70)
                print("PREVIEW ONLY - APPROVAL REQUIRED")
                print("=" * 70)

                print("")
                print(
                    "Replace patch preview created."
                )

                print(
                    "No files were modified."
                )

                print("")

                return

            apply_result = (
                self.apply_replace_engine
                .apply_replace_patch(
                    file_path=target_file,
                    function_name=function_name,
                    class_name=class_name,
                    new_function_source=patch_code,
                    approve=True
                )
            )

            print("\n" + "=" * 70)
            print("STEP 8 - APPLY REPLACE PATCH")
            print("=" * 70)

            print("")
            print(apply_result)
            print("")

            if apply_result.get(
                "status"
            ) == "PATCH_APPLIED":

                self.run_verifier()

                print("\n" + "=" * 70)
                print("SELF EDIT COMPLETE")
                print("=" * 70)

                print("")
                print(
                    "Replace patch applied successfully."
                )

                print(
                    "Backup created successfully."
                )

                print(
                    "Verifier executed."
                )

                print("")

            return
        self.preview_patch(
            target_file,
            patch_code
        )

        validation = self.validate_patch(
            target_file,
            patch_code
        )

        if not validation.get("valid"):
            print("\n" + "=" * 70)
            print("PATCH BLOCKED")
            print("=" * 70)
            print("")
            print("Validation failed.")
            print(validation.get("errors"))
            print("No files were modified.")
            print("")
            return

        if not approve:
            print("\n" + "=" * 70)
            print("PREVIEW ONLY - APPROVAL REQUIRED")
            print("=" * 70)
            print("")
            print("Patch preview created.")
            print("Patch validation passed.")
            print("No files were modified.")
            print("")
            print("To apply this patch, run:")
            print(
                f'python -m agents.self_editing_agent '
                f'--goal "{goal}" '
                f'--target "{target_module}" '
                f'--file "{target_file}" '
                f'--path "{target_path}" '
                f'--approve'
            )
            print("")
            print(f"Request Status: {change_request['status']}")
            print(f"Patch Status: {code_patch['status']}")
            print("")
            return

        apply_result = self.apply_patch(
            approval_text="approve",
            goal=goal,
            target_file=target_file,
            patch_code=patch_code
        )

        if apply_result.get("success"):
            self.run_verifier()

            print("\n" + "=" * 70)
            print("SELF EDIT COMPLETE")
            print("=" * 70)
            print("")
            print("Patch applied successfully.")
            print("Backup was created by SafeCodeEditor.")
            print("Verifier executed.")
            print("")

        else:
            print("\n" + "=" * 70)
            print("APPLY FAILED")
            print("=" * 70)
            print("")
            print(apply_result)
            print("")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="ModirAgent Self Editing Agent"
    )

    parser.add_argument(
        "--goal",
        required=True,
        help="Upgrade goal"
    )

    parser.add_argument(
        "--approve",
        action="store_true",
        help="Apply patch after preview and validation"
    )

    parser.add_argument(
        "--target",
        default="providers.runway_video_provider",
        help="Target module for dependency graph"
    )

    parser.add_argument(
        "--file",
        default="providers/runway_video_provider.py",
        help="Target file to patch"
    )

    parser.add_argument(
        "--path",
        default="providers",
        help="Target folder/path for project analysis"
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    agent = SelfEditingAgent(".")

    agent.run(
        goal=args.goal,
        target_module=args.target,
        core_files=[
            args.file
        ],
        impact_files=[
            "core/video_provider_router.py",
            "engines/video_generation_engine.py",
            "pipelines/full_video_pipeline.py"
        ],
        target_path=args.path,
        approve=args.approve
    )


if __name__ == "__main__":
    main()