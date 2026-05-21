from engines.subtitle_engine import SubtitleEngine
from engines.subtitle_burner import SubtitleBurner
from engines.music_engine import MusicEngine


VIDEO_PATH = "outputs/final_videos/episode_01_final_selfcare_video.mp4"

NARRATION_TEXT = """
Your skin looks tired because you're missing THIS.
Make this simple glow mask tonight for soft hydrated radiant skin naturally.
"""

VIDEO_DURATION_SECONDS = 15.16

MUSIC_FILE = "assets/music/soft_feminine_bg.mp3"


def main():
    print("\n[1] Generating subtitles...")

    subtitle_engine = SubtitleEngine()
    subtitles = subtitle_engine.create_subtitles(
        narration_text=NARRATION_TEXT,
        duration=VIDEO_DURATION_SECONDS,
        base_name="episode_01_publish_ready",
    )

    print("[2] Burning subtitles...")

    subtitled_video = "outputs/postprocessed/episode_01_with_subtitles.mp4"

    burner = SubtitleBurner()
    burner.burn_ass_subtitles(
        input_video=VIDEO_PATH,
        subtitle_file=subtitles["ass"],
        output_video=subtitled_video,
    )

    print("[3] Adding background music...")

    final_video = "outputs/postprocessed/episode_01_publish_ready.mp4"

    music_engine = MusicEngine()
    music_engine.add_background_music(
        input_video=subtitled_video,
        music_file=MUSIC_FILE,
        output_video=final_video,
        music_volume=0.35,
    )

    print("\nDONE")
    print("Final publish-ready video:", final_video)


if __name__ == "__main__":
    main()