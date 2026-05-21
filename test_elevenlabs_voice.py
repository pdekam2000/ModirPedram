from providers.elevenlabs_voice_provider import ElevenLabsVoiceProvider


def main():
    narrator = ElevenLabsVoiceProvider()

    text = """
    He found the tape recorder still playing in the dark.
    But the voice on the tape was not from the past.
    It was describing exactly what he was doing right now.
    """

    audio_path = narrator.generate_voice(
        text=text,
        output_path="outputs/audio/test_narration.mp3",
    )

    print("\nDONE")
    print("Audio file:", audio_path)


if __name__ == "__main__":
    main()