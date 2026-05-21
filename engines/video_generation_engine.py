from core.video_provider_router import (
    VideoProviderRouter
)


class VideoGenerationEngine:

    def __init__(self):

        self.video_router = (
            VideoProviderRouter()
        )

    def generate_videos(
        self,
        video_prompts,
    ):

        print("\n[2] Generating video clips...")

        downloaded_clips = (
            self.video_router
            .generate_clips(
                video_prompts
            )
        )

        return downloaded_clips