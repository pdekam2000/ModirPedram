import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from engines.video_generation_engine import (
    VideoGenerationEngine
)
from engines.trend_engine import TrendEngine
from engines.video_prompt_engine import VideoPromptEngine
from engines.narration_engine import NarrationEngine
from engines.audio_sync_engine import AudioSyncEngine
from core.topic_memory_engine import TopicMemoryEngine
from core.content_series_planner import ContentSeriesPlanner
from core.timeline_engine import TimelineEngine
from core.video_provider_router import VideoProviderRouter

from engines.viral_hook_engine import ViralHookEngine
from engines.subtitle_engine import SubtitleEngine
from engines.subtitle_burner import SubtitleBurner
from engines.music_engine import MusicEngine
from engines.audio_finish_engine import AudioFinishEngine
from engines.ingredient_overlay_engine import IngredientOverlayEngine
from engines.hook_overlay_engine import HookOverlayEngine
from engines.thumbnail_engine import ThumbnailEngine
from engines.seo_package_engine import SEOPackageEngine
from engines.auto_publishing_engine import AutoPublishingEngine
from engines.ai_performance_analyzer import AIPerformanceAnalyzer
from engines.auto_optimization_loop_engine import AutoOptimizationLoopEngine
from engines.ai_memory_learning_engine import AIMemoryLearningEngine
from engines.final_assembly_engine import (
    FinalAssemblyEngine
)
from utils.ffmpeg_clip_audio_merger import FFmpegClipAudioMerger
from utils.final_cinematic_assembler import FinalCinematicAssembler


load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


FFMPEG_PATH = r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")

STUDIO_TOPIC = os.getenv("STUDIO_TOPIC", "").strip()
STUDIO_PLATFORM = os.getenv("STUDIO_PLATFORM", "").strip()
STUDIO_MODE = os.getenv("STUDIO_MODE", "").strip()
STUDIO_VIDEO_TYPE = os.getenv("STUDIO_VIDEO_TYPE", "").strip()
STUDIO_MUSIC_SOURCE = os.getenv("STUDIO_MUSIC_SOURCE", "local_default").strip() or "local_default"
STUDIO_MUSIC_FILE = os.getenv("STUDIO_MUSIC_FILE", "").strip()


def get_trend_topic():

    trend_engine = TrendEngine()

    if STUDIO_TOPIC:

        print("\n" + "=" * 80)
        print("[RUN STUDIO]")
        print("=" * 80)

        print("[Run Studio] Custom topic received from UI.")
        print("[Run Studio] Topic:", STUDIO_TOPIC)
        print("[Run Studio] Platform:", STUDIO_PLATFORM)
        print("[Run Studio] Mode:", STUDIO_MODE)
        print("[Run Studio] Video Type:", STUDIO_VIDEO_TYPE)
        print("[Run Studio] Music Source:", STUDIO_MUSIC_SOURCE)

        if STUDIO_MUSIC_FILE:
            print("[Run Studio] Music File:", STUDIO_MUSIC_FILE)

        return trend_engine.generate_topic(
            custom_topic=STUDIO_TOPIC
        )

    topic_memory = TopicMemoryEngine()
    max_attempts = 10

    for attempt in range(1, max_attempts + 1):

        print(f"[Topic Memory] Attempt {attempt}/{max_attempts}")

        trend = trend_engine.generate_topic()
        topic = trend["topic"]

        if topic_memory.topic_exists(topic):
            print(f"[Topic Memory] Duplicate topic rejected: {topic}")
            continue

        topic_memory.add_topic(
            topic=topic,
            source="trend_engine"
        )

        print(f"[Topic Memory] New topic saved: {topic}")

        return trend

    emergency_topic = {
        "topic": f"unique skincare trend ritual {RUN_ID}",
        "title": "A Fresh Skincare Ritual To Try Today",
        "ingredients": [
            {"name": "Clean Skin", "amount": "1 routine"},
            {"name": "Skincare Tool", "amount": "1"},
        ],
    }

    topic_memory.add_topic(
        topic=emergency_topic["topic"],
        source="emergency_fallback"
    )

    return emergency_topic


def add_viral_hook_to_first_segment(timeline, viral_hook):

    if timeline.segments:
        timeline.segments[0].narration = (
            f"{viral_hook}\n\n"
            f"{timeline.segments[0].narration}"
        )

    return timeline


def apply_music(topic, title, episode_folder, subtitled_video):

    print("\n[7] Adding music...")

    music_video = f"outputs/full_test/{episode_folder}/with_music.mp4"
    selected_music_file = "assets/music/soft_feminine_bg.mp3"

    if STUDIO_MUSIC_SOURCE == "no_music":

        print("[Music] No music selected. Skipping background music.")
        return subtitled_video

    if STUDIO_MUSIC_SOURCE == "local_mp3":

        if STUDIO_MUSIC_FILE and Path(STUDIO_MUSIC_FILE).exists():
            selected_music_file = STUDIO_MUSIC_FILE
            print(f"[Music] Using local MP3: {selected_music_file}")
        else:
            print("[Music] Local MP3 missing. Falling back to default music.")

    elif STUDIO_MUSIC_SOURCE == "suno_ai":

        print("[Music] Suno AI selected.")

        try:
            from providers.suno_music_provider import SunoMusicProvider

            suno_provider = SunoMusicProvider()

            selected_music_file = suno_provider.generate_background_music(
                topic=topic,
                title=title,
                output_dir=f"outputs/full_test/{episode_folder}/music",
            )

            print(f"[Music] Suno music ready: {selected_music_file}")

        except Exception as e:
            print(f"[Music] Suno provider unavailable or failed: {e}")
            print("[Music] Falling back to default local music.")
            selected_music_file = "assets/music/soft_feminine_bg.mp3"

    else:
        print("[Music] Using default local background music.")

    MusicEngine().add_background_music(
        input_video=subtitled_video,
        music_file=selected_music_file,
        output_video=music_video,
    )

    return music_video


def main():

    print("\n" + "=" * 80)
    print("FULL AI VIDEO PIPELINE")
    print("=" * 80)

    trend = get_trend_topic()

    topic = trend["topic"]
    title = trend["title"]
    ingredients = trend["ingredients"]

    print("\n[TREND TOPIC]")
    print("Title:", title)
    print("Topic:", topic)
    print("Ingredients:", ingredients)

    planner = ContentSeriesPlanner()
    episode = planner.get_episode(1)

    viral_hook_engine = ViralHookEngine()
    viral_package = viral_hook_engine.generate_full_package(topic)

    viral_hook = viral_package["hook"]
    thumbnail_text = viral_package["thumbnail_text"]
    caption_hook = viral_package["caption_hook"]

    print("\n[VIRAL PACKAGE]")
    print("Hook:", viral_hook)
    print("Thumbnail:", thumbnail_text)
    print("Caption Hook:", caption_hook)

    video_prompt_engine = VideoPromptEngine()

    prompt_data = video_prompt_engine.build_video_prompts(
        topic=topic,
        brand_intro=episode.brand_intro,
    )

    video_prompts = prompt_data["video_prompts"]
    direction_data = prompt_data["direction_data"]

    timeline_engine = TimelineEngine()
    timeline = timeline_engine.build_selfcare_timeline()
    timeline = add_viral_hook_to_first_segment(timeline, viral_hook)

    episode_folder = f"test_run_{RUN_ID}"

    narration_engine = NarrationEngine()

    voice_files = narration_engine.generate_narration(
        timeline=timeline,
        episode_folder=episode_folder,
    )

    video_generation_engine = (
       VideoGenerationEngine()
    )

    downloaded_clips = (
      video_generation_engine
      .generate_videos(
        video_prompts
      )
    )

    audio_sync_engine = AudioSyncEngine(
        ffmpeg_path=FFMPEG_PATH
    )

    synced_files = (
       audio_sync_engine.sync_clip_audio(
        downloaded_clips=downloaded_clips,
        voice_files=voice_files,
        episode_folder=episode_folder,
      )
    )

    final_assembly_engine = (
    FinalAssemblyEngine(
        ffmpeg_path=FFMPEG_PATH
    )
   )

    assembled_video = (
    final_assembly_engine
    .assemble_video(
        synced_files=synced_files,
        episode_folder=episode_folder,
      )
    )

    narration_text = "\n".join(
        [segment.narration for segment in timeline.segments]
    )

    print("\n[5] Generating subtitles...")

    subtitle_engine = SubtitleEngine()

    subtitles = subtitle_engine.create_subtitles(
        narration_text=narration_text,
        duration=30,
        base_name=f"{episode_folder}_subtitles",
    )

    print("\n[6] Burning subtitles...")

    subtitled_video = f"outputs/full_test/{episode_folder}/with_subtitles.mp4"

    SubtitleBurner().burn_ass_subtitles(
        input_video=assembled_video,
        subtitle_file=subtitles["ass"],
        output_video=subtitled_video,
    )

    music_video = apply_music(
        topic=topic,
        title=title,
        episode_folder=episode_folder,
        subtitled_video=subtitled_video,
    )

    print("\n[8] Smoothing audio ending...")

    smooth_video = f"outputs/full_test/{episode_folder}/smooth_audio.mp4"

    AudioFinishEngine().smooth_audio_finish(
        input_video=music_video,
        output_video=smooth_video,
    )

    print("\n[9] Adding ingredient overlay...")

    ingredient_video = f"outputs/full_test/{episode_folder}/with_ingredients.mp4"

    IngredientOverlayEngine().add_ingredient_overlay(
        input_video=smooth_video,
        output_video=ingredient_video,
        ingredients=ingredients,
    )

    print("\n[10] Adding hook overlay...")

    final_video = f"outputs/full_test/{episode_folder}/FINAL_PUBLISH_READY.mp4"

    hook_overlay_text = viral_hook.upper().replace(".", "").replace("'", "")
    hook_overlay_text = hook_overlay_text.replace(" BECAUSE ", "\\NBECAUSE ")

    HookOverlayEngine().add_hook_overlay(
        input_video=ingredient_video,
        output_video=final_video,
        hook_text=hook_overlay_text,
    )

    print("\n[11] Generating thumbnail...")

    thumbnail_path = ThumbnailEngine().generate_thumbnail(
        input_video=final_video,
        thumbnail_text=thumbnail_text,
        output_name=f"{episode_folder}_thumbnail",
    )

    print("\n[12] Generating SEO package...")

    seo_engine = SEOPackageEngine()

    seo_package = seo_engine.build_package(
        topic=topic,
        hook=viral_hook,
        thumbnail_text=thumbnail_text,
        episode_number=1,
    )

    seo_file = seo_engine.save_package(
        package=seo_package,
        filename=f"{episode_folder}_seo_package",
    )

    print("\n[13] Building publishing package...")

    publish_package = AutoPublishingEngine().build_publish_package(
        seo_package_path=seo_file,
        video_path=final_video,
        thumbnail_path=thumbnail_path,
    )

    publish_file = AutoPublishingEngine().save_publish_package(
        package=publish_package,
        filename=f"{episode_folder}_publish_package",
    )

    print("\n[14] Performance report...")

    analyzer = AIPerformanceAnalyzer()
    report = analyzer.build_report(video_name=final_video)

    report_file = analyzer.save_report(
        report=report,
        filename=f"{episode_folder}_performance_report",
    )

    print("\n[15] Optimization strategy...")

    optimizer = AutoOptimizationLoopEngine()
    strategy = optimizer.build_optimization_strategy(report)

    strategy_file = optimizer.save_strategy(
        strategy=strategy,
        filename=f"{episode_folder}_optimization",
    )

    print("\n[16] Saving AI memory...")

    memory = AIMemoryLearningEngine()

    memory.add_video_result(
        video_name=final_video,
        topic=topic,
        hook=viral_hook,
        thumbnail_text=thumbnail_text,
        score=report["overall_score"],
        rating=report["rating"],
    )

    print("\n" + "=" * 80)
    print("FULL PIPELINE COMPLETE")
    print("=" * 80)

    print("Final Video:", final_video)
    print("Thumbnail:", thumbnail_path)
    print("SEO Package:", seo_file)
    print("Publish Package:", publish_file)
    print("Performance Report:", report_file)
    print("Optimization:", strategy_file)


if __name__ == "__main__":
    main()