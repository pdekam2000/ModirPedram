import json
from pathlib import Path
from dotenv import load_dotenv
import os


load_dotenv()


class ProviderRegistryEngine:

    def __init__(self):

        self.config_dir = Path("config")

        self.registry_file = (
            self.config_dir /
            "provider_registry.json"
        )

        self.active_file = (
            self.config_dir /
            "active_providers.json"
        )

        self.ensure_files_exist()

    def ensure_files_exist(self):

        self.config_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.registry_file.exists():

            default_registry = {

                "video": [

                    {
                        "name": "hailuo",
                        "display_name": "Hailuo / MiniMax",
                        "api_key_env": "",
                        "mode": "browser",
                        "enabled": True
                    },

                    {
                        "name": "runway",
                        "display_name": "RunwayML",
                        "api_key_env": "RUNWAY_API_KEY",
                        "mode": "api",
                        "enabled": False
                    },

                    {
                        "name": "luma",
                        "display_name": "Luma AI",
                        "api_key_env": "LUMA_API_KEY",
                        "mode": "api",
                        "enabled": False
                    },

                    {
                        "name": "kling",
                        "display_name": "Kling AI",
                        "api_key_env": "KLING_API_KEY",
                        "mode": "api",
                        "enabled": False
                    }
                ],

                "music": [

                    {
                        "name": "suno",
                        "display_name": "Suno AI",
                        "api_key_env": "SUNO_API_KEY",
                        "mode": "api",
                        "enabled": False
                    }
                ],

                "voice": [

                    {
                        "name": "elevenlabs",
                        "display_name": "ElevenLabs",
                        "api_key_env": "ELEVENLABS_API_KEY",
                        "mode": "api",
                        "enabled": True
                    },

                    {
                        "name": "openai_tts",
                        "display_name": "OpenAI TTS",
                        "api_key_env": "OPENAI_API_KEY",
                        "mode": "api",
                        "enabled": False
                    }
                ],

                "llm": [

                    {
                        "name": "openai",
                        "display_name": "OpenAI",
                        "api_key_env": "OPENAI_API_KEY",
                        "mode": "api",
                        "enabled": True
                    },

                    {
                        "name": "claude",
                        "display_name": "Claude",
                        "api_key_env": "CLAUDE_API_KEY",
                        "mode": "api",
                        "enabled": False
                    },

                    {
                        "name": "gemini",
                        "display_name": "Gemini",
                        "api_key_env": "GEMINI_API_KEY",
                        "mode": "api",
                        "enabled": False
                    },

                    {
                        "name": "deepseek",
                        "display_name": "DeepSeek",
                        "api_key_env": "DEEPSEEK_API_KEY",
                        "mode": "api",
                        "enabled": False
                    }
                ]
            }

            with open(
                self.registry_file,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    default_registry,
                    f,
                    indent=4
                )

        if not self.active_file.exists():

            default_active = {

                "video": "hailuo",
                "music": "suno",
                "voice": "elevenlabs",
                "llm": "openai"
            }

            with open(
                self.active_file,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    default_active,
                    f,
                    indent=4
                )

    def load_registry(self):

        with open(
            self.registry_file,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    def load_active(self):

        with open(
            self.active_file,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    def save_active(
        self,
        active_config
    ):

        with open(
            self.active_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                active_config,
                f,
                indent=4
            )

    def get_provider_names(
        self,
        category
    ):

        registry = self.load_registry()

        return [

            provider["name"]

            for provider in registry.get(
                category,
                []
            )

            if provider.get(
                "enabled",
                True
            )
        ]

    def get_provider_info(
        self,
        category,
        provider_name
    ):

        registry = self.load_registry()

        for provider in registry.get(
            category,
            []
        ):

            if provider["name"] == provider_name:
                return provider

        return None

    def api_key_exists(
        self,
        category,
        provider_name
    ):

        provider = self.get_provider_info(
            category,
            provider_name
        )

        if not provider:
            return False

        mode = provider.get(
            "mode",
            "api"
        )

        if mode == "browser":
            return True

        env_name = provider.get(
            "api_key_env"
        )

        if not env_name:
            return False

        return bool(
            os.getenv(env_name)
        )

    def get_provider_status(
        self,
        category,
        provider_name
    ):

        provider = self.get_provider_info(
            category,
            provider_name
        )

        if not provider:
            return "UNKNOWN"

        mode = provider.get(
            "mode",
            "api"
        )

        if mode == "browser":
            return "BROWSER MODE"

        if self.api_key_exists(
            category,
            provider_name
        ):
            return "API OK"

        return "NO API KEY"

    def print_summary(self):

        registry = self.load_registry()
        active = self.load_active()

        print("\n" + "=" * 60)
        print("PROVIDER REGISTRY")
        print("=" * 60)

        for category, providers in registry.items():

            print(f"\n[{category.upper()}]")

            for provider in providers:

                name = provider["name"]

                active_mark = ""

                if active.get(category) == name:
                    active_mark = "  <-- ACTIVE"

                status = self.get_provider_status(
                    category,
                    name
                )

                print(
                    f"- {name} "
                    f"({status})"
                    f"{active_mark}"
                )


if __name__ == "__main__":

    engine = ProviderRegistryEngine()

    engine.print_summary()