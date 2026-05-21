from pathlib import Path
import subprocess
import shutil


class FFmpegStitcher:
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path

    def check_ffmpeg(self) -> bool:
        return shutil.which(self.ffmpeg_path) is not None

    def stitch_clips(self, clip_paths, output_path: str):
        if not self.check_ffmpeg():
            raise RuntimeError(
                "FFmpeg not found. Please install FFmpeg and make sure it is available in PATH."
            )

        if not clip_paths or len(clip_paths) < 2:
            raise ValueError("At least 2 clips are required for stitching.")

        clips = [Path(p).resolve() for p in clip_paths]
        output = Path(output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)

        for clip in clips:
            if not clip.exists():
                raise FileNotFoundError(f"Clip not found: {clip}")

        list_file = output.parent / "ffmpeg_concat_list.txt"

        with open(list_file, "w", encoding="utf-8") as f:
            for clip in clips:
                safe_path = str(clip).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(output),
        ]

        print("[FFmpegStitcher] Stitching clips...")
        print("[FFmpegStitcher] Output:", output)

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            print("[FFmpegStitcher] Direct copy failed. Trying re-encode mode...")

            cmd_reencode = [
                self.ffmpeg_path,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(output),
            ]

            result = subprocess.run(
                cmd_reencode,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    "FFmpeg stitching failed:\n"
                    + result.stderr
                )

        print("[FFmpegStitcher] Final video saved:", output)
        return str(output)