from core.provider_registry_engine import ProviderRegistryEngine
from content_brain.execution.provider_cancel_wiring import call_with_optional_cancel_check


class VideoProviderRouter:

    def __init__(self):
        self.registry = ProviderRegistryEngine()
        self.active = self.registry.load_active()

    def get_active_video_provider(self):
        return self.active.get("video", "hailuo_browser")

    def generate_clips(
        self,
        prompts,
        *,
        provider_override: str | None = None,
        cancel_check=None,
        runway_obs=None,
    ):
        provider_name = provider_override or self.get_active_video_provider()
        if provider_override:
            provider_name = str(provider_override).strip().lower()
            if provider_name == "hailuo":
                provider_name = "hailuo_browser"
            if provider_name == "runway_api":
                provider_name = "runway"

        print("\n" + "=" * 60)
        print("VIDEO PROVIDER ROUTER")
        print("=" * 60)
        print(f"[Router] Active video provider: {provider_name}")

        if provider_name in ["hailuo", "hailuo_browser"]:
            from orchestrators.hailuo_multi_clip_orchestrator import (
                HailuoMultiClipOrchestrator,
            )

            orchestrator = HailuoMultiClipOrchestrator()

            return call_with_optional_cancel_check(orchestrator.run, prompts, cancel_check=cancel_check)

        if provider_name == "runway_browser":
            from orchestrators.runway_browser_orchestrator import (
                RunwayBrowserOrchestrator,
            )
            from providers.runway_browser_support import log_runway_wait_config

            wait_seconds, _source = log_runway_wait_config()
            orchestrator = RunwayBrowserOrchestrator(
                wait_seconds=wait_seconds,
                runway_obs=runway_obs,
            )

            return call_with_optional_cancel_check(orchestrator.run, prompts, cancel_check=cancel_check)

        if provider_name == "minimax_api":
            from providers.minimax_video_provider import (
                MiniMaxVideoProvider,
            )

            provider = MiniMaxVideoProvider()
            return provider.generate_clips(prompts)

        if provider_name in ["runway", "runway_api"]:
            from providers.runway_video_provider import (
                RunwayVideoProvider,
            )

            provider = RunwayVideoProvider()
            return call_with_optional_cancel_check(provider.generate_clips, prompts, cancel_check=cancel_check)

        raise ValueError(
            f"Unsupported video provider: {provider_name}"
        )