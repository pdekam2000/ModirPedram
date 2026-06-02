import re


class RuntimeCommandParser:

    """
    Runtime Command Parser V1

    Purpose:
    - Parse structured runtime commands
    - Convert Goal Box text into runtime payloads

    Format:

    FILE: ...
    FUNCTION: ...
    CLASS: ...

    CHANGE:
    ...
    """

    def __init__(self):
        pass

    # =====================================================
    # CLEAN
    # =====================================================

    def clean_value(self, value):

        if value is None:
            return ""

        return value.strip()

    # =====================================================
    # EXTRACT FIELD
    # =====================================================

    def extract_field(
        self,
        text,
        field_name
    ):

        pattern = (
            rf"{field_name}\s*:\s*(.+)"
        )

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if not match:
            return None

        return self.clean_value(
            match.group(1)
        )

    # =====================================================
    # EXTRACT CHANGE BLOCK
    # =====================================================

    def extract_change_block(self, text):

        pattern = r"CHANGE\s*:\s*(.*)"

        match = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL
        )

        if not match:
            return None

        return self.clean_value(
            match.group(1)
        )

    # =====================================================
    # BUILD PAYLOAD
    # =====================================================

    def build_payload(self, text):

        target_file = self.extract_field(
            text,
            "FILE"
        )

        function_name = self.extract_field(
            text,
            "FUNCTION"
        )

        class_name = self.extract_field(
            text,
            "CLASS"
        )

        change_request = self.extract_change_block(
            text
        )

        return {
            "target_file":
                target_file,

            "function_name":
                function_name,

            "class_name":
                class_name,

            "change_request":
                change_request,
        }

    # =====================================================
    # VALIDATE
    # =====================================================

    def validate_payload(self, payload):

        errors = []

        if not payload.get(
            "target_file"
        ):
            errors.append(
                "Missing FILE field."
            )

        if not payload.get(
            "function_name"
        ):
            errors.append(
                "Missing FUNCTION field."
            )

        if not payload.get(
            "change_request"
        ):
            errors.append(
                "Missing CHANGE block."
            )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    # =====================================================
    # PARSE
    # =====================================================

    def parse(self, text):

        payload = self.build_payload(text)

        validation = self.validate_payload(
            payload
        )

        return {
            "success":
                validation["valid"],

            "payload":
                payload,

            "validation":
                validation,
        }


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    parser = RuntimeCommandParser()

    sample_text = """
FILE: execution/apply_replace_patch_test_target.py
FUNCTION: demo_replace_target
CLASS: Demo

CHANGE:
Change print message to HELLO WORLD
"""

    result = parser.parse(
        sample_text
    )

    print("")
    print("=" * 60)
    print("RUNTIME COMMAND PARSER TEST")
    print("=" * 60)

    print(result)