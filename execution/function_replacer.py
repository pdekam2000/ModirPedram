from pathlib import Path
import ast
import textwrap

from execution.function_extractor import FunctionExtractor

class FunctionReplacer:

    """
    Safely replaces an existing Python function or class method
    in memory first. It does NOT write to disk directly.
    """

    def __init__(self, project_root="."):

        self.project_root = Path(project_root).resolve()
        self.extractor = FunctionExtractor(project_root)

    def validate_new_function(
        self,
        new_function_source
    ):

        cleaned_source = textwrap.dedent(
            new_function_source
        ).strip()

        try:
            ast.parse(cleaned_source)

        except SyntaxError as error:
            raise SyntaxError(
                f"New function has invalid syntax: {error}"
            )

        tree = ast.parse(cleaned_source)

        function_nodes = [
            node
            for node in tree.body
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef
                )
            )
        ]

        if len(function_nodes) != 1:
            raise ValueError(
                "New function source must contain exactly one function."
            )

        return function_nodes[0], cleaned_source

    def apply_indentation(
        self,
        new_function_source,
        old_function_source
    ):

        old_lines = old_function_source.splitlines()

        if not old_lines:
            return new_function_source

        first_old_line = old_lines[0]
        indent = first_old_line[
            :len(first_old_line) - len(first_old_line.lstrip())
        ]

        new_lines = new_function_source.splitlines()

        indented_lines = []

        for line in new_lines:

            if line.strip():
                indented_lines.append(indent + line)
            else:
                indented_lines.append(line)

        return "\n".join(indented_lines)

    def replace_in_source(
        self,
        source,
        start_line,
        end_line,
        new_function_source
    ):

        lines = source.splitlines()

        before = lines[:start_line - 1]
        after = lines[end_line:]

        new_lines = new_function_source.rstrip().splitlines()

        updated_lines = before + new_lines + after

        return "\n".join(updated_lines) + "\n"

    def replace_function(
        self,
        file_path,
        function_name,
        new_function_source,
        class_name=None
    ):

        original_source = self.extractor.read_source(file_path)

        extracted = self.extractor.extract(
            file_path=file_path,
            function_name=function_name,
            class_name=class_name
        )

        new_node, cleaned_new_source = self.validate_new_function(
            new_function_source
        )

        if new_node.name != function_name:
            raise ValueError(
                f"Replacement function name mismatch. "
                f"Expected '{function_name}', got '{new_node.name}'."
            )

        indented_new_source = self.apply_indentation(
            new_function_source=cleaned_new_source,
            old_function_source=extracted["source"]
        )

        updated_source = self.replace_in_source(
            source=original_source,
            start_line=extracted["start_line"],
            end_line=extracted["end_line"],
            new_function_source=indented_new_source
        )

        try:
            ast.parse(updated_source)

        except SyntaxError as error:
            raise SyntaxError(
                f"Updated file would be invalid Python: {error}"
            )

        return {
            "file_path": extracted["file_path"],
            "function_name": function_name,
            "class_name": class_name,
            "start_line": extracted["start_line"],
            "end_line": extracted["end_line"],
            "old_source": extracted["source"],
            "new_source": indented_new_source,
            "updated_source": updated_source,
        }


if __name__ == "__main__":

    replacer = FunctionReplacer(".")

    test_file = "execution/function_replacer_test_target.py"

    Path(test_file).write_text(
        '''class Demo:

    def demo_replace_target(self):

        print("OLD VERSION")

        return False
''',
        encoding="utf-8"
    )

    new_function = '''
def demo_replace_target(self):

    print("This function was replaced safely in memory.")

    return True
'''

    result = replacer.replace_function(
        file_path=test_file,
        function_name="demo_replace_target",
        class_name="Demo",
        new_function_source=new_function
    )

    print("\n" + "=" * 60)
    print("FUNCTION REPLACED IN MEMORY")
    print("=" * 60)

    print("\nOld Source:\n")
    print(result["old_source"])

    print("\nNew Source:\n")
    print(result["new_source"])

    print("\nUpdated File Preview:\n")
    print(result["updated_source"])