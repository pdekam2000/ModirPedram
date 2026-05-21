from pathlib import Path

from core.content_series_planner import ContentSeriesPlanner
from core.selfcare_content_engine import SelfcareContentEngine
from core.timeline_engine import TimelineEngine

from engines.viral_hook_engine import ViralHookEngine

from providers.elevenlabs_voice_provider import ElevenLabsVoiceProvider

from orchestrators.hailuo_multi_clip_orchestrator import (
    HailuoMultiClipOrchestrator,
)

from utils.ffmpeg_clip_audio_merger import FFmpegClipAudioMerger
from utils.final_cinematic_assembler import FinalCinematicAssembler


FFMPEG_PATH = r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
EPISODE_NUMBER = 1


def add_brand_intro_to_prompts(prompts, brand_intro):
    updated_prompts = []

    for index, prompt in enumerate(prompts, start=1):
        if index == 1:
            updated_prompt = f"""
BRAND INTRO FIRST 5 SECONDS:
{brand_intro}

After the 5-second branded opening, continue with:

{prompt}
""".strip()
        else:
            updated_prompt = f"""
VISUAL BRAND CONSISTENCY:
Keep the same clean feminine brand identity from the opening:
{brand_intro}

{prompt}
""".strip()

        updated_prompts.append(updated_prompt)

    return updated_prompts


def add_viral_hook_to_first_segment(timeline, viral_hook):
    if not timeline.segments:
        return timeline

    first_segment = timeline.segments[0]

    first_segment.narration = f"{viral_hook}\n\n{first_segment.narration}"

    return timeline


def main():
    print("\n" + "=" * 80)
    print("EPISODE-BASED SELFCARE VIDEO FACTORY")
    print("=" * 80)

    planner = ContentSeriesPlanner()
    episode = planner.get_episode(EPISODE_NUMBER)

    print("\n[EPISODE]")
    print("Series:", episode.series_name)
    print("Episode:", episode.episode_number)
    print("Category:", episode.category)
    print("Topic:", episode.topic)

    viral_hook_engine = ViralHookEngine()
    viral_package = viral_hook_engine.generate_full_package(episode.topic)

    viral_hook = viral_package["hook"]
    thumbnail_text = viral_package["thumbnail_text"]
    caption_hook = viral_package["caption_hook"]

    print("\n[VIRAL PACKAGE]")
    print("Hook:", viral_hook)
    print("Thumbnail Text:", thumbnail_text)
    print("Caption Hook:", caption_hook)

    content_engine = SelfcareContentEngine()

    plan = content_engine.build_mask_video(
        topic=episode.topic
    )

    video_prompts = add_brand_intro_to_prompts(
        prompts=plan.video_prompts,
        brand_intro=episode.brand_intro,
    )

    timeline_engine = TimelineEngine()
    timeline = timeline_engine.build_selfcare_timeline()

    timeline = add_viral_hook_to_first_segment(
        timeline=timeline,
        viral_hook=viral_hook,
    )

    print("\n[STEP 1] Generating timeline narration...")

    narrator = ElevenLabsVoiceProvider(
        voice_id="EXAVITQu4vr4xnSDxMaL"
    )

    episode_folder = f"episode_{episode.episode_number:02d}"

    audio_dir = Path("outputs/audio") / episode_folder
    audio_dir.mkdir(parents=True, exist_ok=True)

    voice_files = []

    for segment in timeline.segments:
        voice_file = narrator.generate_voice(
            text=segment.narration,
            output_path=str(
                audio_dir / f"clip_{segment.clip_number}_voice.mp3"
            ),
        )
        voice_files.append(voice_file)

    print("\n[STEP 2] Generating Hailuo video clips...")

    orchestrator = HailuoMultiClipOrchestrator(wait_seconds=150)

    downloaded_clips = orchestrator.run(video_prompts)

    print("\n[STEP 3] Syncing voice with each clip...")

    synced_dir = Path("outputs/synced_clips") / episode_folder
    synced_dir.mkdir(parents=True, exist_ok=True)

    merger = FFmpegClipAudioMerger(
        ffmpeg_path=FFMPEG_PATH
    )

    synced_files = []

    for index, (clip, voice) in enumerate(
        zip(downloaded_clips, voice_files),
        start=1,
    ):
        synced_file = merger.merge_clip_audio(
            video_path=str(clip),
            audio_path=str(voice),
            output_path=str(
                synced_dir / f"synced_clip_{index}.mp4"
            ),
        )
        synced_files.append(synced_file)

    print("\n[STEP 4] Final cinematic assembly...")

    assembler = FinalCinematicAssembler(
        ffmpeg_path=FFMPEG_PATH
    )

    final_video = assembler.assemble(
        clip_paths=synced_files,
        output_path=(
            f"outputs/final_videos/"
            f"episode_{episode.episode_number:02d}_final_selfcare_video.mp4"
        ),
    )

    print("\n" + "=" * 80)
    print("EPISODE COMPLETE")
    print("=" * 80)

    print("Title:", plan.title)
    print("Category:", episode.category)
    print("Topic:", episode.topic)
    print("Viral Hook:", viral_hook)
    print("Thumbnail Text:", thumbnail_text)
    print("Caption Hook:", caption_hook)
    print("Final video:", final_video)


if __name__ == "__main__":
    main()