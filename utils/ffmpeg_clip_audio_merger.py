from pathlib import Path
import subprocess


class FFmpegClipAudioMerger:
    def __init__(self, ffmpeg_path):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = str(Path(ffmpeg_path).with_name("ffprobe.exe"))

    def get_duration(self, file_path):
        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

        return float(result.stdout.strip())

    def build_atempo_filter(self, speed):
        if speed <= 2.0:
            return f"atempo={speed:.4f}"

        filters = []
        remaining = speed

        while remaining > 2.0:
            filters.append("atempo=2.0")
            remaining /= 2.0

        filters.append(f"atempo={remaining:.4f}")
        return ",".join(filters)

    def merge_clip_audio(
        self,
        video_path,
        audio_path,
        output_path,
        end_safety_seconds=0.25,
        fade_out_seconds=0.20,
    ):
        video_path = Path(video_path)
        audio_path = Path(audio_path)
        output_path = Path(output_path)

        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio not found: {audio_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        video_duration = self.get_duration(video_path)
        audio_duration = self.get_duration(audio_path)

        target_audio_duration = max(
            0.5,
            video_duration - end_safety_seconds,
        )

        print("\n[FFmpegClipAudioMerger]")
        print("Video duration:", round(video_duration, 2))
        print("Audio duration:", round(audio_duration, 2))
        print("Target audio duration:", round(target_audio_duration, 2))

        if audio_duration > target_audio_duration:
            speed = audio_duration / target_audio_duration
            audio_filter = self.build_atempo_filter(speed)
            fade_start = max(
                0.1,
                target_audio_duration - fade_out_seconds,
            )

            final_audio_filter = (
                f"[1:a]{audio_filter},"
                f"afade=t=out:st={fade_start:.2f}:d={fade_out_seconds:.2f},"
                f"apad=pad_dur=0.3[aout]"
            )

            print("Audio mode: speed-adjusted")
            print("Speed factor:", round(speed, 3))

        else:
            fade_start = max(
                0.1,
                audio_duration - fade_out_seconds,
            )

            final_audio_filter = (
                f"[1:a]"
                f"afade=t=out:st={fade_start:.2f}:d={fade_out_seconds:.2f},"
                f"apad=pad_dur=1.0[aout]"
            )

            print("Audio mode: natural + padded")

        cmd = [
            self.ffmpeg_path,
            "-y",

            "-i", str(video_path),
            "-i", str(audio_path),

            "-filter_complex", final_audio_filter,

            "-map", "0:v:0",
            "-map", "[aout]",

            "-c:v", "copy",
            "-c:a", "aac",

            "-t", f"{video_duration:.2f}",

            str(output_path),
        ]

        subprocess.run(cmd, check=True)

        print("Saved synced clip:", output_path)

        return str(output_path)