import argparse

from agents.project_upgrade_agent import ProjectUpgradeAgent
from agents.change_request_agent import ChangeRequestAgent
from agents.code_generation_agent import CodeGenerationAgent
from agents.verifier_agent import VerifierAgent

from core.dependency_graph_engine import DependencyGraphEngine
from core.upgrade_planner_engine import UpgradePlannerEngine

from execution.patch_preview_engine import PatchPreviewEngine
from execution.patch_validator import PatchValidator
from execution.apply_patch_engine import ApplyPatchEngine


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
        self.preview_engine = PatchPreviewEngine(project_root)
        self.validator = PatchValidator(project_root)
        self.apply_engine = ApplyPatchEngine(project_root)
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

        patch = code_patch.get("patch", {})
        patch_code = patch.get("code", "")
        patch_operation = patch.get("operation", "NO_PATCH")

        if patch_operation != "APPEND_FUNCTION":
            print("\n" + "=" * 70)
            print("PATCH BLOCKED")
            print("=" * 70)
            print("")
            print(f"Unsupported patch operation: {patch_operation}")
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