from config.config_loader import (
    ConfigLoader,
)


class ConfigInjectionEngine:
    def __init__(self):
        loader = ConfigLoader()

        self.config = loader.load()

    def get_video_config(self):
        return self.config["video"]

    def get_audio_config(self):
        return self.config["audio"]

    def get_subtitle_config(self):
        return self.config["subtitles"]

    def get_branding_config(self):
        return self.config["branding"]

    def get_hook_config(self):
        return self.config["hooks"]

    def get_continuity_config(self):
        return self.config["continuity"]

    def get_director_config(self):
        return self.config["director"]

    def get_seo_config(self):
        return self.config["seo"]

    def get_optimization_config(self):
        return self.config["optimization"]

    def get_publishing_config(self):
        return self.config["publishing"]

    def get_ui_config(self):
        return self.config["ui"]

    def print_summary(self):
        print("\nCONFIG INJECTION SUMMARY\n")

        sections = [
            "video",
            "audio",
            "subtitles",
            "branding",
            "hooks",
            "continuity",
            "director",
            "seo",
            "optimization",
            "publishing",
            "ui",
        ]

        for section in sections:
            print("=" * 60)

            print(section.upper())

            print(
                self.config[section]
            )


if __name__ == "__main__":
    engine = (
        ConfigInjectionEngine()
    )

    engine.print_summary()