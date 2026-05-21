import subprocess


class RunnerService:

    def __init__(self, project_root):
        self.project_root = project_root

    def run_command_stream(
        self,
        command,
        env=None,
        on_line=None
    ):
        process = subprocess.Popen(
            command,
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env
        )

        for line in process.stdout:
            if on_line:
                on_line(line)

        process.wait()

        return process.returncode