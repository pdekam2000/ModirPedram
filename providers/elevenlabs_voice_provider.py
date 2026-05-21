import os
from pathlib import Path

import requests
from dotenv import load_dotenv


class ElevenLabsVoiceProvider:
    def __init__(
        self,
        voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
        model_id: str = "eleven_multilingual_v2",
        output_format: str = "mp3_44100_128",
    ):
        load_dotenv()

        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = voice_id
        self.model_id = model_id
        self.output_format = output_format

        if not self.api_key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY not found in .env file."
            )

    def generate_voice(
        self,
        text: str,
        output_path: str = "outputs/audio/narration.mp3",
    ) -> str:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/"
            f"{self.voice_id}?output_format={self.output_format}"
        )

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.85,
                "style": 0.35,
                "use_speaker_boost": True,
            },
        }

        print("[ElevenLabs] Generating narration...")

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=120,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"ElevenLabs API error {response.status_code}:\n"
                f"{response.text}"
            )

        output_file.write_bytes(response.content)

        print("[ElevenLabs] Audio saved:", output_file)
        return str(output_file)