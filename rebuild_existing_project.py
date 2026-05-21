from pathlib import Path

from utils.ffmpeg_clip_audio_merger import (
    FFmpegClipAudioMerger,
)

from utils.final_cinematic_assembler import (
    FinalCinematicAssembler,
)

from engines.subtitle_engine import SubtitleEngine
from engines.subtitle_burner import SubtitleBurner

from engines.music_engine import MusicEngine

from engines.audio_finish_engine import (
    AudioFinishEngine,
)

from engines.ingredient_overlay_engine import (
    IngredientOverlayEngine,
)


FFMPEG_PATH = (
    r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
)

EPISODE_FOLDER = "episode_01"

def find_latest_hailuo_clips(count=3):
    clips = sorted(
        Path(".").rglob("hailuo_clip_*.mp4"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if len(clips) < count:
        raise FileNotFoundError(
            f"Only found {len(clips)} Hailuo clips, need {count}"
        )

    latest = list(reversed(clips[:count]))
    return [str(p) for p in latest]


VIDEO_CLIPS = find_latest_hailuo_clips(count=3)

VOICE_FILES = [
    "outputs/audio/episode_01/clip_1_voice.mp3",
    "outputs/audio/episode_01/clip_2_voice.mp3",
    "outputs/audio/episode_01/clip_3_voice.mp3",
]

NARRATION_TEXT = """
Your skin looks tired because you're missing THIS.
Make this simple glow mask tonight for soft hydrated radiant skin naturally.
"""

INGREDIENTS = [
    {
        "name": "Yogurt",
        "amount": "1 tbsp",
    },
    {
        "name": "Honey",
        "amount": "1 tsp",
    },
    {
        "name": "Oats",
        "amount": "1 tbsp",
    },
]

MUSIC_FILE = "assets/music/soft_feminine_bg.mp3"


def main():
    print("\n" + "=" * 80)
    print("REBUILD EXISTING PROJECT")
    print("=" * 80)

    synced_dir = (
        Path("outputs/rebuild/synced")
    )
    synced_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    merger = FFmpegClipAudioMerger(
        ffmpeg_path=FFMPEG_PATH
    )

    synced_files = []

    print("\n[1] Rebuilding synced clips...")

    for index, (clip, voice) in enumerate(
        zip(VIDEO_CLIPS, VOICE_FILES),
        start=1,
    ):
        synced_file = merger.merge_clip_audio(
            video_path=clip,
            audio_path=voice,
            output_path=str(
                synced_dir /
                f"synced_clip_{index}.mp4"
            ),
        )

        synced_files.append(synced_file)

    print("\n[2] Final assembly...")

    assembler = FinalCinematicAssembler(
        ffmpeg_path=FFMPEG_PATH
    )

    assembled_video = assembler.assemble(
        clip_paths=synced_files,
        output_path=(
            "outputs/rebuild/"
            "assembled_video.mp4"
        ),
    )

    print("\n[3] Generating subtitles...")

    subtitle_engine = SubtitleEngine()

    subtitles = subtitle_engine.create_subtitles(
        narration_text=NARRATION_TEXT,
        duration=15,
        base_name="rebuild_video",
    )

    print("\n[4] Burning subtitles...")

    subtitled_video = (
        "outputs/rebuild/"
        "subtitled_video.mp4"
    )

    burner = SubtitleBurner()

    burner.burn_ass_subtitles(
        input_video=assembled_video,
        subtitle_file=subtitles["ass"],
        output_video=subtitled_video,
    )

    print("\n[5] Adding music...")

    music_video = (
        "outputs/rebuild/"
        "music_video.mp4"
    )

    music_engine = MusicEngine()

    music_engine.add_background_music(
        input_video=subtitled_video,
        music_file=MUSIC_FILE,
        output_video=music_video,
        music_volume=0.35,
    )

    print("\n[6] Smoothing ending...")

    smooth_video = (
        "outputs/rebuild/"
        "smooth_video.mp4"
    )

    audio_finish_engine = (
        AudioFinishEngine()
    )

    audio_finish_engine.smooth_audio_finish(
        input_video=music_video,
        output_video=smooth_video,
    )

    print("\n[7] Adding ingredient overlay...")

    final_video = (
        "outputs/rebuild/"
        "final_publish_ready.mp4"
    )

    overlay_engine = (
        IngredientOverlayEngine()
    )

    overlay_engine.add_ingredient_overlay(
        input_video=smooth_video,
        output_video=final_video,
        ingredients=INGREDIENTS,
    )

    print("\n" + "=" * 80)
    print("REBUILD COMPLETE")
    print("=" * 80)

    print("Final video:", final_video)


if __name__ == "__main__":
    main()