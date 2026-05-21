from pathlib import Path
import subprocess


class SubtitleBurner:
    def __init__(self):
        self.ffmpeg_path = r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"

    def burn_ass_subtitles(self, input_video, subtitle_file, output_video):
        input_video = Path(input_video)
        subtitle_file = Path(subtitle_file)
        output_video = Path(output_video)

        if not input_video.exists():
            raise FileNotFoundError(f"Input video not found: {input_video}")

        if not subtitle_file.exists():
            raise FileNotFoundError(f"Subtitle file not found: {subtitle_file}")

        if not Path(self.ffmpeg_path).exists():
            raise FileNotFoundError(f"FFmpeg not found: {self.ffmpeg_path}")

        output_video.parent.mkdir(parents=True, exist_ok=True)

        subtitle_path = str(subtitle_file.resolve()).replace("\\", "/").replace(":", "\\:")

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(input_video),
            "-vf",
            f"ass='{subtitle_path}'",
            "-c:a",
            "copy",
            str(output_video),
        ]

        print("[SubtitleBurner] Running FFmpeg...")
        subprocess.run(cmd, check=True)

        print(f"[SubtitleBurner] Saved subtitled video: {output_video}")
        return str(output_video)


if __name__ == "__main__":
    burner = SubtitleBurner()

    input_video = "outputs/final_videos/episode_01_final_selfcare_video.mp4"
    subtitle_file = "outputs/subtitles/viral_test.ass"
    output_video = "outputs/subtitled/test_subtitled_video.mp4"

    burner.burn_ass_subtitles(
        input_video=input_video,
        subtitle_file=subtitle_file,
        output_video=output_video,
    )