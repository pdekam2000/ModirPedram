from pathlib import Path
import subprocess


class AudioFinishEngine:
    def __init__(self):
        self.ffmpeg_path = (
            r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
        )

    def smooth_audio_finish(
        self,
        input_video,
        output_video,
        audio_end_early_seconds=0.6,
        fade_duration=0.5,
    ):
        input_video = Path(input_video)
        output_video = Path(output_video)

        if not input_video.exists():
            raise FileNotFoundError(
                f"Video not found: {input_video}"
            )

        output_video.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        duration_cmd = [
            self.ffmpeg_path,
            "-i",
            str(input_video),
        ]

        result = subprocess.run(
            duration_cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )

        duration_line = ""

        for line in result.stderr.splitlines():
            if "Duration" in line:
                duration_line = line
                break

        if not duration_line:
            raise RuntimeError("Could not detect video duration")

        duration_text = (
            duration_line.split("Duration:")[1]
            .split(",")[0]
            .strip()
        )

        h, m, s = duration_text.split(":")
        total_duration = (
            int(h) * 3600
            + int(m) * 60
            + float(s)
        )

        fade_start = (
            total_duration
            - audio_end_early_seconds
            - fade_duration
        )

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(input_video),

            "-af",
            (
                f"afade=t=out:"
                f"st={fade_start}:"
                f"d={fade_duration}"
            ),

            "-c:v",
            "copy",

            "-c:a",
            "aac",

            "-shortest",

            str(output_video),
        ]

        print("[AudioFinishEngine] Smoothing ending audio...")

        subprocess.run(cmd, check=True)

        print(
            f"[AudioFinishEngine] Saved: {output_video}"
        )

        return str(output_video)


if __name__ == "__main__":
    engine = AudioFinishEngine()

    input_video = (
        "outputs/postprocessed/"
        "episode_01_publish_ready.mp4"
    )

    output_video = (
        "outputs/postprocessed/"
        "episode_01_publish_ready_smooth.mp4"
    )

    engine.smooth_audio_finish(
        input_video=input_video,
        output_video=output_video,
        audio_end_early_seconds=0.7,
        fade_duration=0.5,
    )