from core.selfcare_content_engine import SelfcareContentEngine
from providers.elevenlabs_voice_provider import ElevenLabsVoiceProvider


def main():
    content_engine = SelfcareContentEngine()

    plan = content_engine.build_mask_video(
        topic="calming yogurt, honey, and oat mask for tired-looking skin"
    )

   narrator = ElevenLabsVoiceProvider(
    voice_id="EXAVITQu4vr4xnSDxMaL"
  )

    audio_path = narrator.generate_voice(
        text=plan.voiceover,
        output_path="outputs/audio/selfcare_narration.mp3",
    )

    print("\nDONE")
    print("Title:", plan.title)
    print("Audio:", audio_path)


if __name__ == "__main__":
    main()