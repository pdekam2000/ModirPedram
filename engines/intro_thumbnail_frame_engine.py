from pathlib import Path
import subprocess


class IntroThumbnailFrameEngine:
    def __init__(self):
        self.ffmpeg_path = (
            r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
        )

    def create_intro_frame_video(
        self,
        input_video,
        output_video,
        hook_text,
        duration=1.2,
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

        hook_text = (
            hook_text
            .replace(":", "")
            .replace("'", "")
        )

        filter_complex = (
            "drawbox="
            "x=0:y=0:w=iw:h=ih:"
            "color=black@0.30:t=fill,"
            "drawtext="
            "fontfile='C\\:/Windows/Fonts/arialbd.ttf':"
            f"text='{hook_text}':"
            "fontcolor=white:"
            "fontsize=72:"
            "borderw=4:"
            "bordercolor=black:"
            "x=(w-text_w)/2:"
            "y=(h-text_h)/2"
        )

        cmd = [
            self.ffmpeg_path,
            "-y",

            "-i",
            str(input_video),

            "-vf",
            filter_complex,

            "-t",
            str(duration),

            "-c:a",
            "copy",

            str(output_video),
        ]

        print(
            "[IntroThumbnailFrameEngine] "
            "Creating intro thumbnail frame..."
        )

        subprocess.run(
            cmd,
            check=True,
        )

        print(
            "[IntroThumbnailFrameEngine] "
            f"Saved: {output_video}"
        )

        return str(output_video)


if __name__ == "__main__":
    engine = IntroThumbnailFrameEngine()

    input_video = (
        "outputs/postprocessed/"
        "episode_01_final_hooked_video.mp4"
    )

    output_video = (
        "outputs/postprocessed/"
        "episode_01_intro_thumbnail.mp4"
    )

    hook_text = (
        "YOUR SKIN NEEDS THIS"
    )

    engine.create_intro_frame_video(
        input_video=input_video,
        output_video=output_video,
        hook_text=hook_text,
        duration=1.5,
    )