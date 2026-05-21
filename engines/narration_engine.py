from pathlib import Path

from providers.elevenlabs_voice_provider import ElevenLabsVoiceProvider


class NarrationEngine:

    def __init__(self):
        self.voice_provider = ElevenLabsVoiceProvider(
            voice_id="EXAVITQu4vr4xnSDxMaL"
        )

    def generate_narration(self, timeline, episode_folder):

        print("\n[1] Generating ElevenLabs narration...")

        audio_dir = Path("outputs/audio") / episode_folder
        audio_dir.mkdir(parents=True, exist_ok=True)

        voice_files = []

        for segment in timeline.segments:

            voice_file = self.voice_provider.generate_voice(
                text=segment.narration,
                output_path=str(
                    audio_dir / f"clip_{segment.clip_number}_voice.mp3"
                ),
            )

            voice_files.append(voice_file)

        return voice_files