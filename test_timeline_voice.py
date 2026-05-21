from pathlib import Path

from core.timeline_engine import TimelineEngine
from providers.elevenlabs_voice_provider import ElevenLabsVoiceProvider


def main():
    timeline_engine = TimelineEngine()
    timeline = timeline_engine.build_selfcare_timeline()

    narrator = ElevenLabsVoiceProvider(
        voice_id="EXAVITQu4vr4xnSDxMaL"
    )

    output_dir = Path("outputs/audio/timeline")
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_files = []

    for segment in timeline.segments:
        print("\n" + "=" * 80)
        print(f"Generating voice for Clip {segment.clip_number}")
        print("Scene:", segment.scene_label)
        print("Emotion:", segment.emotion)

        text = (
            f"Voice direction: {segment.emotion}. "
            f"{segment.narration}"
        )

        audio_path = narrator.generate_voice(
            text=text,
            output_path=str(output_dir / f"clip_{segment.clip_number}_voice.mp3"),
        )

        audio_files.append(audio_path)

    print("\nDONE")
    print("Generated timeline audio files:")
    for file in audio_files:
        print(" -", file)


if __name__ == "__main__":
    main()