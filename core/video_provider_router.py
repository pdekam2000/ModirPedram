from core.provider_registry_engine import ProviderRegistryEngine


class VideoProviderRouter:

    def __init__(self):
        self.registry = ProviderRegistryEngine()
        self.active = self.registry.load_active()

    def get_active_video_provider(self):
        return self.active.get("video", "hailuo_browser")

    def generate_clips(self, prompts):
        provider_name = self.get_active_video_provider()

        print("\n" + "=" * 60)
        print("VIDEO PROVIDER ROUTER")
        print("=" * 60)
        print(f"[Router] Active video provider: {provider_name}")

        if provider_name in ["hailuo", "hailuo_browser"]:
            from orchestrators.hailuo_multi_clip_orchestrator import (
                HailuoMultiClipOrchestrator,
            )

            orchestrator = HailuoMultiClipOrchestrator(
                wait_seconds=150
            )

            return orchestrator.run(prompts)

        if provider_name == "runway_browser":
            from orchestrators.runway_browser_orchestrator import (
                RunwayBrowserOrchestrator,
            )

            orchestrator = RunwayBrowserOrchestrator(
                wait_seconds=180
            )

            return orchestrator.run(prompts)

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
            return provider.generate_clips(prompts)

        raise ValueError(
            f"Unsupported video provider: {provider_name}"
        )