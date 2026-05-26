from pathlib import Path
import ast


class ProjectContextAgent:
    """
    Project Context Agent V1

    Purpose:
    - Read target file
    - Extract classes
    - Extract functions
    - Extract imports
    - Read dependency graph
    - Build context report

    No file modifications.
    """

    def __init__(self, project_root="."):
        self.project_root = Path(project_root).resolve()

    # =====================================================
    # FILE HELPERS
    # =====================================================

    def resolve_path(
        self,
        relative_path: str
    ) -> Path:

        return (
            self.project_root
            / relative_path
        ).resolve()

    def read_file(
        self,
        relative_path: str
    ) -> str:

        path = self.resolve_path(
            relative_path
        )

        return path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    # =====================================================
    # AST EXTRACTION
    # =====================================================

    def extract_classes(
        self,
        code: str
    ):

        classes = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):

                if isinstance(
                    node,
                    ast.ClassDef
                ):
                    classes.append(
                        node.name
                    )

        except Exception:
            pass

        return sorted(set(classes))

    def extract_functions(
        self,
        code: str
    ):

        functions = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):

                if isinstance(
                    node,
                    ast.FunctionDef
                ):
                    functions.append(
                        node.name
                    )

        except Exception:
            pass

        return sorted(set(functions))

    def extract_imports(
        self,
        code: str
    ):

        imports = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):

                if isinstance(
                    node,
                    ast.Import
                ):
                    for name in node.names:
                        imports.append(
                            name.name
                        )

                if isinstance(
                    node,
                    ast.ImportFrom
                ):
                    if node.module:
                        imports.append(
                            node.module
                        )

        except Exception:
            pass

        return sorted(set(imports))

    # =====================================================
    # DEPENDENCY REPORT
    # =====================================================

    def load_dependency_report(self):

        report = (
            self.project_root
            / "project_brain"
            / "dependency_graph_report.md"
        )

        if not report.exists():
            return "Dependency report not found."

        return report.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    # =====================================================
    # BUILD CONTEXT
    # =====================================================

    def build_context(
        self,
        target_file: str
    ):

        code = self.read_file(
            target_file
        )

        context = {
            "target_file":
                target_file,

            "classes":
                self.extract_classes(
                    code
                ),

            "functions":
                self.extract_functions(
                    code
                ),

            "imports":
                self.extract_imports(
                    code
                ),

            "dependency_report":
                self.load_dependency_report(),
        }

        return context

    # =====================================================
    # DISPLAY
    # =====================================================

    def print_context(
        self,
        context
    ):

        print("")
        print("=" * 60)
        print("PROJECT CONTEXT")
        print("=" * 60)

        print("")
        print(
            f"FILE: "
            f"{context['target_file']}"
        )

        print("")
        print("CLASSES:")

        for item in context["classes"]:
            print(f" - {item}")

        print("")
        print("FUNCTIONS:")

        for item in context["functions"]:
            print(f" - {item}")

        print("")
        print("IMPORTS:")

        for item in context["imports"]:
            print(f" - {item}")

        print("")

    # =====================================================
    # RUN
    # =====================================================

    def run(
        self,
        target_file
    ):

        context = self.build_context(
            target_file
        )

        self.print_context(
            context
        )

        return context


if __name__ == "__main__":

    agent = ProjectContextAgent(".")

    agent.run(
        "providers/runway_video_provider.py"
    )