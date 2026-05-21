import subprocess
from pathlib import Path


BLOCKED_COMMANDS = [
    "del ",
    "rmdir",
    "remove-item",
    "format",
    "shutdown",
    "restart-computer",
    "rm ",
    "sudo",
    "curl",
    "wget",
]


def is_command_safe(command: str) -> tuple[bool, str]:
    command_lower = command.lower().strip()

    for blocked in BLOCKED_COMMANDS:
        if blocked in command_lower:
            return False, f"Blocked command pattern detected: {blocked}"

    return True, "Command passed safety check."


def run_command(command: str, project_root: str = ".") -> dict:
    root = Path(project_root).resolve()

    safe, message = is_command_safe(command)

    if not safe:
        return {
            "success": False,
            "command": command,
            "stdout": "",
            "stderr": message,
            "return_code": None,
        }

    result = subprocess.run(
        command,
        cwd=root,
        shell=True,
        capture_output=True,
        text=True,
    )

    return {
        "success": result.returncode == 0,
        "command": command,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "return_code": result.returncode,
    }


if __name__ == "__main__":
    test_commands = [
        "python --version",
        "dir",
        "del test.py",
    ]

    for cmd in test_commands:
        result = run_command(cmd)
        print("=" * 60)
        print(f"Command: {cmd}")
        print(f"Success: {result['success']}")
        print(f"Return code: {result['return_code']}")
        print("STDOUT:")
        print(result["stdout"])
        print("STDERR:")
        print(result["stderr"])