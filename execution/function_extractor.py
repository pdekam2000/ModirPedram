from pathlib import Path
import ast


class FunctionExtractor:

    """
    Safely extracts existing functions or methods
    from Python source files.
    """

    def __init__(self, project_root="."):

        self.project_root = Path(project_root).resolve()

    def resolve_path(self, file_path):

        path = Path(file_path)

        if not path.is_absolute():
            path = self.project_root / path

        path = path.resolve()

        if not str(path).startswith(str(self.project_root)):
            raise ValueError(
                "Unsafe path outside project root."
            )

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {path}"
            )

        if path.suffix != ".py":
            raise ValueError(
                "Only Python files are supported."
            )

        return path

    def read_source(self, file_path):

        path = self.resolve_path(file_path)

        return path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    def find_function_node(
        self,
        source,
        function_name,
        class_name=None
    ):

        tree = ast.parse(source)

        if class_name:

            for node in ast.walk(tree):

                if (
                    isinstance(node, ast.ClassDef)
                    and node.name == class_name
                ):

                    for child in node.body:

                        if isinstance(
                            child,
                            (
                                ast.FunctionDef,
                                ast.AsyncFunctionDef
                            )
                        ) and child.name == function_name:

                            return child

            return None

        matches = []

        for node in ast.walk(tree):

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef
                )
            ) and node.name == function_name:

                matches.append(node)

        if len(matches) == 1:
            return matches[0]

        if len(matches) > 1:

            raise ValueError(
                f"Multiple functions named "
                f"'{function_name}' found. "
                f"Provide class_name."
            )

        return None

    def extract(
        self,
        file_path,
        function_name,
        class_name=None
    ):

        source = self.read_source(file_path)

        lines = source.splitlines()

        node = self.find_function_node(
            source=source,
            function_name=function_name,
            class_name=class_name
        )

        if node is None:

            raise ValueError(
                f"Function not found: "
                f"{function_name}"
            )

        start_line = node.lineno

        end_line = getattr(
            node,
            "end_lineno",
            None
        )

        if end_line is None:

            raise RuntimeError(
                "Python 3.8+ required "
                "for end_lineno support."
            )

        function_source = "\n".join(
            lines[start_line - 1:end_line]
        )

        return {
            "file_path": str(
                self.resolve_path(file_path)
            ),
            "function_name": function_name,
            "class_name": class_name,
            "start_line": start_line,
            "end_line": end_line,
            "source": function_source,
        }


if __name__ == "__main__":

    extractor = FunctionExtractor(".")

    result = extractor.extract(
        file_path="execution/function_extractor.py",
        function_name="extract",
        class_name="FunctionExtractor"
    )

    print("\n" + "=" * 60)
    print("FUNCTION EXTRACTED")
    print("=" * 60)

    print(
        f"\nFile: "
        f"{result['file_path']}"
    )

    print(
        f"Function: "
        f"{result['function_name']}"
    )

    print(
        f"Class: "
        f"{result['class_name']}"
    )

    print(
        f"Lines: "
        f"{result['start_line']} "
        f"-> "
        f"{result['end_line']}"
    )

    print("\n" + "=" * 60)
    print("SOURCE")
    print("=" * 60)

    print(result["source"])