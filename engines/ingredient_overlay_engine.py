from pathlib import Path
import subprocess


class IngredientOverlayEngine:
    def __init__(self):
        self.ffmpeg_path = (
            r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
        )

    def format_ass_time(self, seconds):
        cs = int((seconds - int(seconds)) * 100)
        s = int(seconds) % 60
        m = (int(seconds) // 60) % 60
        h = int(seconds) // 3600
        return f"{h}:{m:02}:{s:02}.{cs:02}"

    def get_video_duration(self, input_video):
        cmd = [
            self.ffmpeg_path,
            "-i",
            str(input_video),
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        for line in result.stderr.splitlines():
            if "Duration" in line:
                duration_text = (
                    line.split("Duration:")[1]
                    .split(",")[0]
                    .strip()
                )
                h, m, s = duration_text.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)

        raise RuntimeError("Could not detect video duration")

    def build_ass_overlay(self, ingredients, duration, output_ass):
        output_ass = Path(output_ass)
        output_ass.parent.mkdir(parents=True, exist_ok=True)

        lines = [r"{\b1\fs36}INGREDIENTS{\b0\fs30}"]

        for item in ingredients:
            lines.append(
                f"{item['name']}  -  {item['amount']}"
            )

        text = r"\N".join(lines)

        end_time = self.format_ass_time(duration)

        ass_content = f"""[Script Info]
Title: Ingredient Overlay
ScriptType: v4.00+
PlayResX: 1366
PlayResY: 768

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: IngredientBox,Arial,30,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,1,0,0,0,100,100,0,0,3,2,0,9,0,70,95,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 1,0:00:01.00,{end_time},IngredientBox,,0,70,95,,{{\\fad(300,300)}}{text}
"""

        output_ass.write_text(ass_content, encoding="utf-8")
        return str(output_ass)

    def add_ingredient_overlay(
        self,
        input_video,
        output_video,
        ingredients,
    ):
        input_video = Path(input_video)
        output_video = Path(output_video)

        if not input_video.exists():
            raise FileNotFoundError(
                f"Video not found: {input_video}"
            )

        output_video.parent.mkdir(parents=True, exist_ok=True)

        duration = self.get_video_duration(input_video)

        overlay_ass = Path("outputs/overlays/ingredient_overlay.ass")

        ass_path = self.build_ass_overlay(
            ingredients=ingredients,
            duration=duration,
            output_ass=overlay_ass,
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

        print("[IngredientOverlayEngine] Adding ingredient overlay...")

        subprocess.run(cmd, check=True)

        print(f"[IngredientOverlayEngine] Saved: {output_video}")

        return str(output_video)


if __name__ == "__main__":
    engine = IngredientOverlayEngine()

    input_video = (
        "outputs/postprocessed/"
        "episode_01_publish_ready_smooth.mp4"
    )

    output_video = (
        "outputs/postprocessed/"
        "episode_01_final_brand_video.mp4"
    )

    ingredients = [
        {
            "name": "Yogurt",
            "amount": "1 tbsp",
        },
        {
            "name": "Honey",
            "amount": "1 tsp",
        },
        {
            "name": "Oats",
            "amount": "1 tbsp",
        },
    ]

    engine.add_ingredient_overlay(
        input_video=input_video,
        output_video=output_video,
        ingredients=ingredients,
    )