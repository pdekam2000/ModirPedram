from pathlib import Path
import subprocess

from core.config_injection_engine import ConfigInjectionEngine


class MusicEngine:
    def __init__(self):
        self.ffmpeg_path = (
            r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
        )

        self.config_engine = ConfigInjectionEngine()
        self.audio_config = self.config_engine.get_audio_config()

    def add_background_music(
        self,
        input_video,
        music_file,
        output_video,
        music_volume=None,
    ):
        input_video = Path(input_video)
        music_file = Path(music_file)
        output_video = Path(output_video)

        if not input_video.exists():
            raise FileNotFoundError(f"Video not found: {input_video}")

        if not music_file.exists():
            raise FileNotFoundError(f"Music not found: {music_file}")

        output_video.parent.mkdir(parents=True, exist_ok=True)

        if music_volume is None:
            music_volume = self.audio_config.get("music_volume", 0.14)

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(music_file),
            "-i",
            str(input_video),
            "-filter_complex",
            (
                f"[0:a]volume={music_volume}[bg];"
                f"[1:a][bg]"
                f"amix=inputs=2:"
                f"duration=first:"
                f"dropout_transition=3"
                f"[aout]"
            ),
            "-map",
            "1:v",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output_video),
        ]

        print("[MusicEngine] Adding background music...")
        print(f"[MusicEngine] Music file: {music_file}")
        print(f"[MusicEngine] Volume from config: {music_volume}")

        subprocess.run(cmd, check=True)

        print(f"[MusicEngine] Saved: {output_video}")
        return str(output_video)
