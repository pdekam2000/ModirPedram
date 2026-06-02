import ast
import re
import textwrap


class SemanticPatchEngine:

    """
    Semantic Patch Engine V1

    Applies safe incremental function edits on old_source.
    Validates AST after every operation.
    Never silently falls back to full replacement.
    """

    STRATEGY_SEMANTIC_INCREMENTAL_SAFE = (
        "SEMANTIC_INCREMENTAL_SAFE"
    )
    STRATEGY_FULL_REPLACEMENT_REQUIRED = (
        "FULL_REPLACEMENT_REQUIRED"
    )
    STRATEGY_HIGH_RISK_DESTRUCTIVE = (
        "HIGH_RISK_DESTRUCTIVE"
    )

    STATUS_FAILED = "FAILED_TO_GENERATE"
    STATUS_SUCCESS = "SUCCESS"

    OP_INSERT_AFTER_LINE = "INSERT_AFTER_LINE"
    OP_INSERT_BEFORE_RETURN = "INSERT_BEFORE_RETURN"
    OP_APPEND_TO_FUNCTION = "APPEND_TO_FUNCTION"
    OP_REPLACE_SINGLE_LINE = "REPLACE_SINGLE_LINE"
    OP_ADD_LOGGING = "ADD_LOGGING"
    OP_ADD_TRY_EXCEPT_WRAPPER = "ADD_TRY_EXCEPT_WRAPPER"

    HIGH_RISK_REMOVAL_RATIO = 0.40

    FULL_REWRITE_TRIGGERS = (
        "full rewrite",
        "replace entire function",
        "rewrite entire function",
        "full replacement",
    )

    def validate_ast(self, function_source):

        try:
            cleaned = textwrap.dedent(
                function_source
            ).strip()

            if not cleaned:
                return False

            ast.parse(cleaned)
            return True

        except SyntaxError:
            return False

    def get_base_indent(self, lines):

        if not lines:
            return ""

        first = lines[0]
        return first[: len(first) - len(first.lstrip())]

    def get_body_indent(self, lines):

        base = self.get_base_indent(lines)

        for line in lines[1:]:
            if line.strip():
                return line[: len(line) - len(line.lstrip())]

        return base + "    "

    def find_return_line_index(self, lines):

        indices = []

        for index, line in enumerate(lines):
            stripped = line.strip()

            if stripped.startswith("return "):
                indices.append(index)

        if not indices:
            return None

        return indices[-1]

    def find_print_line_index(self, lines):

        for index, line in enumerate(lines):
            if "print(" in line:
                return index

        return None

    def explicit_full_rewrite_requested(
        self,
        change_request
    ):

        text = change_request.lower()

        return any(
            trigger in text
            for trigger in self.FULL_REWRITE_TRIGGERS
        )

    def plan_operations(
        self,
        change_request,
        old_source
    ):

        if not old_source or not str(old_source).strip():
            return None

        if self.explicit_full_rewrite_requested(
            change_request
        ):
            return {
                "patch_strategy": (
                    self.STRATEGY_FULL_REPLACEMENT_REQUIRED
                ),
                "operations": [],
            }

        text = change_request.lower().strip()
        operations = []

        if "add logging" in text:
            operations.append({
                "op": self.OP_ADD_LOGGING,
            })

        elif "add try except" in text:
            operations.append({
                "op": self.OP_ADD_TRY_EXCEPT_WRAPPER,
            })

        elif "change print message to" in text:
            message = (
                change_request.replace(
                    "Change print message to",
                    "",
                )
                .replace(
                    "change print message to",
                    "",
                )
                .strip()
                .strip('"')
                .strip("'")
            )

            operations.append({
                "op": self.OP_REPLACE_SINGLE_LINE,
                "target": "print",
                "replacement": (
                    f'print("{message}")'
                ),
            })

        elif "return false" in text:
            operations.append({
                "op": self.OP_REPLACE_SINGLE_LINE,
                "target": "return",
                "replacement": "return False",
            })

        elif "return true" in text:
            operations.append({
                "op": self.OP_REPLACE_SINGLE_LINE,
                "target": "return",
                "replacement": "return True",
            })

        else:
            return None

        return {
            "patch_strategy": (
                self.STRATEGY_SEMANTIC_INCREMENTAL_SAFE
            ),
            "operations": operations,
        }

    def apply_insert_after_line(
        self,
        lines,
        line_index,
        content
    ):

        indent = self.get_body_indent(lines)
        new_line = indent + content.lstrip()

        updated = lines[:]
        updated.insert(line_index + 1, new_line)

        return updated

    def apply_insert_before_return(
        self,
        lines,
        content
    ):

        return_index = self.find_return_line_index(
            lines
        )

        if return_index is None:
            return None

        indent = lines[return_index][
            : len(lines[return_index])
            - len(lines[return_index].lstrip())
        ]

        new_line = indent + content.lstrip()

        updated = lines[:]
        updated.insert(return_index, new_line)

        return updated

    def apply_append_to_function(
        self,
        lines,
        content
    ):

        indent = self.get_body_indent(lines)
        new_line = indent + content.lstrip()

        return lines + [new_line]

    def apply_replace_single_line(
        self,
        lines,
        target,
        replacement
    ):

        if target == "print":
            index = self.find_print_line_index(lines)
        elif target == "return":
            index = self.find_return_line_index(lines)
        else:
            index = None

        if index is None:
            return None

        indent = lines[index][
            : len(lines[index])
            - len(lines[index].lstrip())
        ]

        updated = lines[:]
        updated[index] = indent + replacement.lstrip()

        return updated

    def apply_add_logging(self, lines):

        return self.apply_insert_after_line(
            lines=lines,
            line_index=0,
            content='print("LOG: Function started")',
        )

    def apply_add_try_except_wrapper(self, lines):

        if len(lines) < 1:
            return None

        def_line = lines[0]
        body_lines = lines[1:]

        if not body_lines:
            return None

        body_indent = self.get_body_indent(lines)
        inner_indent = body_indent + "    "

        updated = [def_line]
        updated.append(f"{body_indent}try:")

        for line in body_lines:
            if line.strip():
                updated.append(
                    inner_indent + line.lstrip()
                )
            else:
                updated.append("")

        updated.append(
            f"{body_indent}except Exception as e:"
        )
        updated.append(
            f'{inner_indent}print(f"ERROR: {{e}}")'
        )
        updated.append(f"{inner_indent}raise")

        return updated

    def apply_single_operation(self, lines, operation):

        op = operation.get("op")

        if op == self.OP_INSERT_AFTER_LINE:
            return self.apply_insert_after_line(
                lines=lines,
                line_index=operation.get(
                    "line_index",
                    0
                ),
                content=operation.get(
                    "content",
                    ""
                ),
            )

        if op == self.OP_INSERT_BEFORE_RETURN:
            return self.apply_insert_before_return(
                lines=lines,
                content=operation.get(
                    "content",
                    ""
                ),
            )

        if op == self.OP_APPEND_TO_FUNCTION:
            return self.apply_append_to_function(
                lines=lines,
                content=operation.get(
                    "content",
                    ""
                ),
            )

        if op == self.OP_REPLACE_SINGLE_LINE:
            return self.apply_replace_single_line(
                lines=lines,
                target=operation.get("target"),
                replacement=operation.get(
                    "replacement",
                    ""
                ),
            )

        if op == self.OP_ADD_LOGGING:
            return self.apply_add_logging(lines)

        if op == self.OP_ADD_TRY_EXCEPT_WRAPPER:
            return self.apply_add_try_except_wrapper(
                lines
            )

        return None

    def meaningful_lines(self, source):

        lines = []

        for line in source.splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            if stripped.startswith("#"):
                continue

            lines.append(stripped)

        return lines

    def assess_patch_strategy(
        self,
        old_source,
        new_source
    ):

        old_lines = self.meaningful_lines(old_source)
        new_lines = self.meaningful_lines(new_source)

        if not old_lines:
            return (
                self.STRATEGY_SEMANTIC_INCREMENTAL_SAFE
            )

        preserved = sum(
            1 for line in old_lines if line in new_lines
        )

        removal_ratio = 1 - (preserved / len(old_lines))

        if removal_ratio > self.HIGH_RISK_REMOVAL_RATIO:
            return self.STRATEGY_HIGH_RISK_DESTRUCTIVE

        return self.STRATEGY_SEMANTIC_INCREMENTAL_SAFE

    def normalize_lines(self, function_source):

        lines = function_source.splitlines()

        while lines and not lines[0].strip():
            lines.pop(0)

        while lines and not lines[-1].strip():
            lines.pop()

        return lines

    def apply_operations(self, old_source, operations):

        lines = self.normalize_lines(old_source)
        operations_applied = []

        for operation in operations:
            updated_lines = self.apply_single_operation(
                lines,
                operation,
            )

            ast_valid = False

            if updated_lines is not None:
                candidate = "\n".join(updated_lines)
                ast_valid = self.validate_ast(candidate)

            record = {
                "operation": operation,
                "ast_valid_after_step": ast_valid,
            }

            operations_applied.append(record)

            if updated_lines is None or not ast_valid:
                return {
                    "success": False,
                    "status": self.STATUS_FAILED,
                    "message": (
                        "Patch generation failed safely. "
                        "No code was changed."
                    ),
                    "operations_applied": (
                        operations_applied
                    ),
                    "ast_valid_after_each_step": False,
                    "new_function_source": None,
                }

            lines = updated_lines

        new_function_source = "\n".join(lines)

        patch_strategy = self.assess_patch_strategy(
            old_source=old_source,
            new_source=new_function_source,
        )

        if (
            patch_strategy
            == self.STRATEGY_HIGH_RISK_DESTRUCTIVE
        ):
            return {
                "success": False,
                "status": self.STATUS_FAILED,
                "message": (
                    "Patch generation failed safely. "
                    "No code was changed."
                ),
                "patch_strategy": patch_strategy,
                "operations_applied": operations_applied,
                "ast_valid_after_each_step": all(
                    item["ast_valid_after_step"]
                    for item in operations_applied
                ),
                "new_function_source": None,
            }

        return {
            "success": True,
            "status": self.STATUS_SUCCESS,
            "patch_strategy": patch_strategy,
            "operations_applied": operations_applied,
            "ast_valid_after_each_step": all(
                item["ast_valid_after_step"]
                for item in operations_applied
            ),
            "new_function_source": new_function_source,
            "old_source_preserved": True,
        }

    def build_semantic_patch(
        self,
        old_source,
        change_request
    ):

        if not old_source or not str(old_source).strip():
            return {
                "success": False,
                "status": self.STATUS_FAILED,
                "message": (
                    "Patch generation failed safely. "
                    "No code was changed."
                ),
                "operations_applied": [],
                "ast_valid_after_each_step": False,
                "new_function_source": None,
            }

        plan = self.plan_operations(
            change_request=change_request,
            old_source=old_source,
        )

        if plan is None:
            return {
                "success": False,
                "status": self.STATUS_FAILED,
                "message": (
                    "Patch generation failed safely. "
                    "No code was changed."
                ),
                "operations_applied": [],
                "ast_valid_after_each_step": False,
                "new_function_source": None,
            }

        patch_strategy = plan.get("patch_strategy")

        if (
            patch_strategy
            == self.STRATEGY_FULL_REPLACEMENT_REQUIRED
        ):
            return {
                "success": False,
                "status": self.STATUS_FAILED,
                "message": (
                    "Full rewrite requested but semantic "
                    "engine does not auto-generate "
                    "destructive replacements."
                ),
                "patch_strategy": patch_strategy,
                "operations_applied": [],
                "ast_valid_after_each_step": False,
                "new_function_source": None,
            }

        operations = plan.get("operations", [])

        if not operations:
            return {
                "success": False,
                "status": self.STATUS_FAILED,
                "message": (
                    "Patch generation failed safely. "
                    "No code was changed."
                ),
                "patch_strategy": patch_strategy,
                "operations_applied": [],
                "ast_valid_after_each_step": False,
                "new_function_source": None,
            }

        result = self.apply_operations(
            old_source=old_source,
            operations=operations,
        )

        result["patch_strategy"] = patch_strategy

        return result


if __name__ == "__main__":

    engine = SemanticPatchEngine()

    old_source = """
    def demo_replace_target(self):

        print("OLD")

        return False
"""

    tests = [
        "Add logging",
        "Change print message to HELLO",
        "Add try except",
        "Do unknown thing",
    ]

    print("")
    print("=" * 60)
    print("SEMANTIC PATCH ENGINE TEST")
    print("=" * 60)

    for change in tests:
        result = engine.build_semantic_patch(
            old_source=old_source,
            change_request=change,
        )

        print("")
        print("Change:", change)
        print("Success:", result.get("success"))
        print("Strategy:", result.get("patch_strategy"))
        print(
            "AST valid each step:",
            result.get("ast_valid_after_each_step"),
        )
        print(
            "Operations:",
            result.get("operations_applied"),
        )
