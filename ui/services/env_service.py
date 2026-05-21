import os
from pathlib import Path

from dotenv import load_dotenv


class EnvService:

    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.env_file = self.project_root / ".env"
        load_dotenv(self.env_file)

    def build_env(self, extra=None):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        if extra:
            for key, value in extra.items():
                env[key] = str(value)

        return env