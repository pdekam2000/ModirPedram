from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont


class ThumbnailEngine:
    def __init__(self):
        self.ffmpeg_path = (
            r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
        )

        self.output_dir = Path(
            "outputs/thumbnails"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.font_path = (
            r"C:\Windows\Fonts\arialbd.ttf"
        )

    def extract_frame(
        self,
        input_video,
        output_image,
        timestamp="00:00:02",
    ):
        cmd = [
            self.ffmpeg_path,
            "-y",

            "-ss",
            timestamp,

            "-i",
            str(input_video),

            "-vframes",
            "1",

            str(output_image),
        ]

        subprocess.run(
            cmd,
            check=True,
        )

    def add_thumbnail_text(
        self,
        image_path,
        output_path,
        text,
    ):
        image = Image.open(image_path)

        draw = ImageDraw.Draw(image)

        font = ImageFont.truetype(
            self.font_path,
            72,
        )

        text = text.upper()

        bbox = draw.textbbox(
            (0, 0),
            text,
            font=font,
        )

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (
            image.width - text_width
        ) // 2

        y = image.height - 220

        shadow_offset = 5

        draw.text(
            (
                x + shadow_offset,
                y + shadow_offset,
            ),
            text,
            font=font,
            fill=(0, 0, 0),
        )

        draw.text(
            (x, y),
            text,
            font=font,
            fill=(255, 255, 255),
        )

        image.save(output_path)

    def generate_thumbnail(
        self,
        input_video,
        thumbnail_text,
        output_name="thumbnail",
    ):
        temp_frame = (
            self.output_dir /
            "temp_frame.jpg"
        )

        final_thumbnail = (
            self.output_dir /
            f"{output_name}.jpg"
        )

        self.extract_frame(
            input_video=input_video,
            output_image=temp_frame,
        )

        self.add_thumbnail_text(
            image_path=temp_frame,
            output_path=final_thumbnail,
            text=thumbnail_text,
        )

        return str(final_thumbnail)


if __name__ == "__main__":
    engine = ThumbnailEngine()

    input_video = (
        "outputs/postprocessed/"
        "episode_01_final_hooked_video.mp4"
    )

    thumbnail_text = (
        "GLOW OVERNIGHT"
    )

    result = engine.generate_thumbnail(
        input_video=input_video,
        thumbnail_text=thumbnail_text,
        output_name="episode_01_thumbnail",
    )

    print("\nTHUMBNAIL CREATED\n")
    print(result)