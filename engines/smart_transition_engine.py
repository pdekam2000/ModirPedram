from pathlib import Path
import subprocess
import tempfile


class SmartTransitionEngine:
    def __init__(self):
        self.ffmpeg_path = (
            r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
        )

    def build_concat_file(
        self,
        clips,
    ):
        temp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
            encoding="utf-8",
        )

        for clip in clips:
            clip_path = (
                str(Path(clip).resolve())
                .replace("\\", "/")
            )

            temp.write(
                f"file '{clip_path}'\n"
            )

        temp.close()

        return temp.name

    def apply_transitions(
        self,
        clips,
        output_video,
    ):
        if len(clips) < 2:
            raise ValueError(
                "Need at least 2 clips"
            )

        output_video = Path(output_video)

        output_video.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        concat_file = self.build_concat_file(
            clips
        )

        filter_complex = (
            "fade=t=in:st=0:d=0.25,"
            "fade=t=out:st=4.7:d=0.25"
        )

        cmd = [
            self.ffmpeg_path,
            "-y",

            "-f",
            "concat",

            "-safe",
            "0",

            "-i",
            concat_file,

            "-vf",
            filter_complex,

            "-af",
            (
                "afade=t=in:st=0:d=0.20,"
                "afade=t=out:st=14:d=0.30"
            ),

            "-c:v",
            "libx264",

            "-c:a",
            "aac",

            str(output_video),
        ]

        print(
            "[SmartTransitionEngine] "
            "Applying cinematic transitions..."
        )

        subprocess.run(
            cmd,
            check=True,
        )

        print(
            "[SmartTransitionEngine] "
            f"Saved: {output_video}"
        )

        return str(output_video)


if __name__ == "__main__":
    engine = SmartTransitionEngine()

    clips = [
        "outputs/synced_clips/episode_01/synced_clip_1.mp4",
        "outputs/synced_clips/episode_01/synced_clip_2.mp4",
        "outputs/synced_clips/episode_01/synced_clip_3.mp4",
    ]

    output_video = (
        "outputs/postprocessed/"
        "episode_01_transitioned.mp4"
    )

    engine.apply_transitions(
        clips=clips,
        output_video=output_video,
    )