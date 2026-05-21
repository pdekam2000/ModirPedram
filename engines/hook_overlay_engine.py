from pathlib import Path
import subprocess


class HookOverlayEngine:
    def __init__(self):
        self.ffmpeg_path = (
            r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
        )

    def build_ass_file(
        self,
        hook_text,
        output_ass,
    ):
        output_ass = Path(output_ass)

        output_ass.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        ass_content = f"""[Script Info]
Title: Viral Hook Overlay
ScriptType: v4.00+
PlayResX: 1366
PlayResY: 768

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding

Style: Hook,Arial,58,&H00FFFFFF,&H000000FF,&H00000000,&H66000000,1,0,0,0,100,100,0,0,3,3,0,5,80,80,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text

Dialogue: 0,0:00:00.20,0:00:03.20,Hook,,0,0,0,,{{\\fad(200,300)}}{hook_text}
"""

        output_ass.write_text(
            ass_content,
            encoding="utf-8",
        )

        return str(output_ass)

    def add_hook_overlay(
        self,
        input_video,
        output_video,
        hook_text,
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

        ass_file = (
            "outputs/overlays/"
            "hook_overlay.ass"
        )

        ass_path = self.build_ass_file(
            hook_text=hook_text,
            output_ass=ass_file,
        )

        ass_path_ffmpeg = (
            str(Path(ass_path).resolve())
            .replace("\\", "/")
            .replace(":", "\\:")
        )

        cmd = [
            self.ffmpeg_path,
            "-y",

            "-i",
            str(input_video),

            "-vf",
            f"ass='{ass_path_ffmpeg}'",

            "-c:a",
            "copy",

            str(output_video),
        ]

        print(
            "[HookOverlayEngine] "
            "Adding viral hook overlay..."
        )

        subprocess.run(
            cmd,
            check=True,
        )

        print(
            "[HookOverlayEngine] "
            f"Saved: {output_video}"
        )

        return str(output_video)


if __name__ == "__main__":
    engine = HookOverlayEngine()

    input_video = (
        "outputs/postprocessed/"
        "episode_01_final_brand_video.mp4"
    )

    output_video = (
        "outputs/postprocessed/"
        "episode_01_final_hooked_video.mp4"
    )

    hook_text = (
        "YOUR SKIN LOOKS TIRED\\N"
        "BECAUSE YOU'RE MISSING THIS"
    )

    engine.add_hook_overlay(
        input_video=input_video,
        output_video=output_video,
        hook_text=hook_text,
    )