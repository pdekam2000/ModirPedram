import json
from pathlib import Path
from dotenv import load_dotenv
import os


load_dotenv()


class ProviderRegistryEngine:
    TREND_CATEGORY = "trend"
    TREND_ENRICHMENT_CATEGORY = "trend_enrichment"
    ACTIVE_TREND_SOURCES_KEY = "trend_sources"
    ACTIVE_TREND_ENRICHMENT_KEY = "trend_enrichment"

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
                ],

                self.TREND_CATEGORY: [

                    {
                        "name": "mock_trend_provider",
                        "display_name": "Mock Local Seeds",
                        "api_key_env": "",
                        "mode": "local",
                        "enabled": True
                    },

                    {
                        "name": "dataforseo",
                        "display_name": "DataForSEO",
                        "api_key_env": "",
                        "credential_envs": [
                            "DATAFORSEO_LOGIN",
                            "DATAFORSEO_PASSWORD"
                        ],
                        "mode": "api",
                        "enabled": False
                    },

                    {
                        "name": "serpapi",
                        "display_name": "SerpAPI",
                        "api_key_env": "SERPAPI_API_KEY",
                        "mode": "api",
                        "enabled": False
                    }
                ],

                self.TREND_ENRICHMENT_CATEGORY: [

                    {
                        "name": "openai_trend_enricher",
                        "display_name": "OpenAI Trend Enricher",
                        "api_key_env": "OPENAI_API_KEY",
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
                "llm": "openai",
                self.ACTIVE_TREND_SOURCES_KEY: [
                    "mock_trend_provider"
                ],
                self.ACTIVE_TREND_ENRICHMENT_KEY: None
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

    def _resolve_required_env_names(
        self,
        provider
    ):

        credential_envs = provider.get(
            "credential_envs",
            []
        )

        if credential_envs:
            return [
                str(item)
                for item in credential_envs
                if item
            ]

        api_key_env = provider.get(
            "api_key_env"
        )

        if api_key_env:
            return [str(api_key_env)]

        return []

    def credentials_ready(
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

        if mode in ("browser", "local"):
            return True

        env_names = self._resolve_required_env_names(
            provider
        )

        if not env_names:
            return False

        return all(
            bool(os.getenv(env_name))
            for env_name in env_names
        )

    def get_provider_credentials(
        self,
        category,
        provider_name
    ):

        if not self.credentials_ready(
            category,
            provider_name
        ):
            return {}

        provider = self.get_provider_info(
            category,
            provider_name
        )

        if not provider:
            return {}

        credentials = {}

        for env_name in self._resolve_required_env_names(provider):
            value = os.getenv(env_name)

            if value:
                credentials[str(env_name)] = str(value)

        return credentials

    def api_key_exists(
        self,
        category,
        provider_name
    ):

        return self.credentials_ready(
            category,
            provider_name
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

        if mode == "local":
            return "LOCAL MODE"

        if self.credentials_ready(
            category,
            provider_name
        ):
            return "API OK"

        return "NO API KEY"

    def get_active_trend_sources(self):

        active = self.load_active()
        raw = active.get(
            self.ACTIVE_TREND_SOURCES_KEY,
            []
        )

        if isinstance(raw, str):
            raw = [raw] if raw.strip() else []

        if not isinstance(raw, list):
            return []

        registry_names = {
            provider["name"]
            for provider in self.load_registry().get(
                self.TREND_CATEGORY,
                []
            )
        }

        validated = []

        for item in raw:
            name = str(item).strip()

            if name and name in registry_names:
                validated.append(name)

        return validated

    def get_active_trend_enrichment(self):

        active = self.load_active()
        value = active.get(
            self.ACTIVE_TREND_ENRICHMENT_KEY
        )

        if value in (None, "", False):
            return None

        name = str(value).strip()

        if not name:
            return None

        if self.get_provider_info(
            self.TREND_ENRICHMENT_CATEGORY,
            name
        ):
            return name

        return None

    def get_ready_trend_sources(self):

        registry = self.load_registry()
        trend_providers = {
            provider["name"]: provider
            for provider in registry.get(
                self.TREND_CATEGORY,
                []
            )
        }

        ready = []

        for name in self.get_active_trend_sources():
            provider = trend_providers.get(name)

            if not provider:
                continue

            if not provider.get(
                "enabled",
                True
            ):
                continue

            if self.credentials_ready(
                self.TREND_CATEGORY,
                name
            ):
                ready.append(name)

        return ready

    def get_credential_ready_trend_sources(self):
        """Trend providers with valid credentials, regardless of active_providers.json."""
        registry = self.load_registry()
        trend_providers = {
            provider["name"]: provider
            for provider in registry.get(
                self.TREND_CATEGORY,
                []
            )
        }

        ready = []

        for name, provider in trend_providers.items():
            if name == "mock_trend_provider":
                continue

            if not provider.get(
                "enabled",
                True
            ):
                continue

            if self.credentials_ready(
                self.TREND_CATEGORY,
                name
            ):
                ready.append(name)

        return ready

    def get_ready_trend_enrichment(self):

        name = self.get_active_trend_enrichment()

        if not name:
            return None

        provider = self.get_provider_info(
            self.TREND_ENRICHMENT_CATEGORY,
            name
        )

        if not provider:
            return None

        if not provider.get(
            "enabled",
            True
        ):
            return None

        if not self.credentials_ready(
            self.TREND_ENRICHMENT_CATEGORY,
            name
        ):
            return None

        return name

    def _is_active_provider(
        self,
        category,
        provider_name,
        active
    ):

        if category == self.TREND_CATEGORY:
            return provider_name in self.get_active_trend_sources()

        if category == self.TREND_ENRICHMENT_CATEGORY:
            return self.get_active_trend_enrichment() == provider_name

        return active.get(category) == provider_name

    def print_summary(self):

        registry = self.load_registry()
        active = self.load_active()

        print("\n" + "=" * 60)
        print("PROVIDER REGISTRY")
        print("=" * 60)
        print(
            f"\nActive trend sources: "
            f"{self.get_active_trend_sources()}"
        )
        print(
            f"Ready trend sources: "
            f"{self.get_ready_trend_sources()}"
        )
        print(
            f"Active trend enrichment: "
            f"{self.get_active_trend_enrichment()}"
        )
        print(
            f"Ready trend enrichment: "
            f"{self.get_ready_trend_enrichment()}"
        )

        for category, providers in registry.items():

            print(f"\n[{category.upper()}]")

            for provider in providers:

                name = provider["name"]

                active_mark = ""

                if self._is_active_provider(
                    category,
                    name,
                    active
                ):
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
