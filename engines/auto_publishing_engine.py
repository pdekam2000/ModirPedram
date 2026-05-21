import json
from pathlib import Path
from datetime import datetime, timedelta


class AutoPublishingEngine:
    def __init__(self):
        self.output_dir = Path(
            "outputs/publishing"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def build_schedule(
        self,
        days_ahead=1,
        hour=19,
        minute=0,
    ):
        publish_time = (
            datetime.now()
            + timedelta(days=days_ahead)
        )

        publish_time = publish_time.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )

        return str(publish_time)

    def build_platform_package(
        self,
        platform,
        title,
        description,
        hashtags,
        thumbnail_path,
        video_path,
    ):
        return {
            "platform": platform,

            "title": title,

            "description": description,

            "hashtags": hashtags,

            "thumbnail": thumbnail_path,

            "video": video_path,
        }

    def build_publish_package(
        self,
        seo_package_path,
        video_path,
        thumbnail_path,
    ):
        with open(
            seo_package_path,
            "r",
            encoding="utf-8",
        ) as f:
            seo = json.load(f)

        hashtags_string = " ".join(
            seo["hashtags"]
        )

        package = {
            "created_at": str(
                datetime.now()
            ),

            "scheduled_publish_time": (
                self.build_schedule()
            ),

            "platforms": [
                self.build_platform_package(
                    platform="Instagram Reels",

                    title=seo["title"],

                    description=(
                        seo[
                            "instagram_caption"
                        ]
                    ),

                    hashtags=hashtags_string,

                    thumbnail_path=(
                        thumbnail_path
                    ),

                    video_path=video_path,
                ),

                self.build_platform_package(
                    platform="YouTube Shorts",

                    title=seo["title"],

                    description=(
                        seo[
                            "youtube_shorts_description"
                        ]
                    ),

                    hashtags=hashtags_string,

                    thumbnail_path=(
                        thumbnail_path
                    ),

                    video_path=video_path,
                ),

                self.build_platform_package(
                    platform="TikTok",

                    title=seo["title"],

                    description=(
                        seo[
                            "tiktok_caption"
                        ]
                    ),

                    hashtags=hashtags_string,

                    thumbnail_path=(
                        thumbnail_path
                    ),

                    video_path=video_path,
                ),
            ],
        }

        return package

    def save_publish_package(
        self,
        package,
        filename,
    ):
        path = (
            self.output_dir /
            f"{filename}.json"
        )

        with open(
            path,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                package,
                f,
                indent=4,
                ensure_ascii=False,
            )

        return str(path)


if __name__ == "__main__":
    engine = AutoPublishingEngine()

    package = (
        engine.build_publish_package(
            seo_package_path=(
                "outputs/seo_packages/"
                "episode_01_seo_package.json"
            ),

            video_path=(
                "outputs/postprocessed/"
                "episode_01_final_hooked_video.mp4"
            ),

            thumbnail_path=(
                "outputs/thumbnails/"
                "episode_01_thumbnail.jpg"
            ),
        )
    )

    saved = (
        engine.save_publish_package(
            package,
            filename=(
                "episode_01_publish_package"
            ),
        )
    )

    print("\nAUTO PUBLISH PACKAGE\n")

    print(json.dumps(
        package,
        indent=4,
        ensure_ascii=False,
    ))

    print("\nSaved package:")
    print(saved)