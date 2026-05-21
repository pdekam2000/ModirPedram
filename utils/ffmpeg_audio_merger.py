from pathlib import Path
import subprocess
import shutil


class FFmpegAudioMerger:
    def __init__(self, ffmpeg_path: str):
        self.ffmpeg_path = ffmpeg_path

    def check_ffmpeg(self):
        return shutil.which(self.ffmpeg_path) or Path(self.ffmpeg_path).exists()

    def merge_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ):
        if not self.check_ffmpeg():
            raise RuntimeError("FFmpeg not found.")

        video = Path(video_path).resolve()
        audio = Path(audio_path).resolve()
        output = Path(output_path).resolve()

        output.parent.mkdir(parents=True, exist_ok=True)

        if not video.exists():
            raise FileNotFoundError(f"Video not found: {video}")

        if not audio.exists():
            raise FileNotFoundError(f"Audio not found: {audio}")

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(video),
            "-i",
            str(audio),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output),
        ]

        print("[FFmpegAudioMerger] Merging audio with video...")
        print("[FFmpegAudioMerger] Output:", output)

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "FFmpeg audio merge failed:\n"
                + result.stderr
            )

        print("[FFmpegAudioMerger] Final video saved:")
        print(output)

        return str(output)