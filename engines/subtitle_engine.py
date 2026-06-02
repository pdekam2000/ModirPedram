from pathlib import Path
import re

DEFAULT_HIGHLIGHT_KEYWORDS = (
    "secret",
    "hidden",
    "important",
    "never",
    "always",
    "stop",
    "watch",
)


class SubtitleEngine:
    def __init__(self, output_dir="outputs/subtitles", highlight_keywords=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if highlight_keywords is not None:
            self.highlight_words = [
                str(word).strip().lower()
                for word in highlight_keywords
                if str(word).strip()
            ]
        else:
            self.highlight_words = list(DEFAULT_HIGHLIGHT_KEYWORDS)

    def split_text(self, text, max_words=4):
        words = text.strip().split()
        chunks = []

        for i in range(0, len(words), max_words):
            chunks.append(" ".join(words[i:i + max_words]))

        return chunks

    def format_srt_time(self, seconds):
        ms = int((seconds - int(seconds)) * 1000)
        s = int(seconds) % 60
        m = (int(seconds) // 60) % 60
        h = int(seconds) // 3600

        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    def format_ass_time(self, seconds):
        cs = int((seconds - int(seconds)) * 100)

        s = int(seconds) % 60
        m = (int(seconds) // 60) % 60
        h = int(seconds) // 3600

        return f"{h}:{m:02}:{s:02}.{cs:02}"

    def style_word(self, word):
        clean_word = re.sub(r"[^\w]", "", word.lower())

        if clean_word in self.highlight_words:
            return (
                r"{\c&H00FFFF&"
                r"\bord3"
                r"\shad0"
                r"\fscx120"
                r"\fscy120}"
                + word +
                r"{\r}"
            )

        return word

    def style_caption(self, text):
        words = text.split()
        styled = [self.style_word(word) for word in words]
        return " ".join(styled)

    def generate_srt(self, narration_text, duration, filename="subtitles.srt"):
        chunks = self.split_text(narration_text)

        if not chunks:
            return None

        segment_duration = duration / len(chunks)

        lines = []

        for idx, chunk in enumerate(chunks, start=1):
            start = (idx - 1) * segment_duration
            end = idx * segment_duration

            lines.append(str(idx))
            lines.append(
                f"{self.format_srt_time(start)} --> {self.format_srt_time(end)}"
            )
            lines.append(chunk.upper())
            lines.append("")

        path = self.output_dir / filename
        path.write_text("\n".join(lines), encoding="utf-8")

        return str(path)

    def generate_ass(self, narration_text, duration, filename="subtitles.ass"):
        chunks = self.split_text(narration_text)

        if not chunks:
            return None

        segment_duration = duration / len(chunks)

        header = r"""[Script Info]
Title: Viral TikTok Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding

Style: Default,Arial,78,&H00FFFFFF,&H0000FFFF,&H00000000,&H66000000,1,0,0,0,100,100,0,0,1,5,0,2,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []

        for idx, chunk in enumerate(chunks):
            start = idx * segment_duration
            end = (idx + 1) * segment_duration

            styled_chunk = self.style_caption(chunk.upper())

            dialogue = (
                f"Dialogue: 0,"
                f"{self.format_ass_time(start)},"
                f"{self.format_ass_time(end)},"
                f"Default,,0,0,0,,"
                f"{{\\fad(80,80)}}"
                f"{styled_chunk}"
            )

            events.append(dialogue)

        path = self.output_dir / filename

        path.write_text(
            header + "\n".join(events),
            encoding="utf-8"
        )

        return str(path)

    def create_subtitles(
        self,
        narration_text,
        duration,
        base_name="final_selfcare_video"
    ):
        srt_path = self.generate_srt(
            narration_text=narration_text,
            duration=duration,
            filename=f"{base_name}.srt"
        )

        ass_path = self.generate_ass(
            narration_text=narration_text,
            duration=duration,
            filename=f"{base_name}.ass"
        )

        return {
            "srt": srt_path,
            "ass": ass_path
        }


if __name__ == "__main__":
    engine = SubtitleEngine()

    test_text = (
        "Watch this hidden secret tonight "
        "because it is always important to stop and learn."
    )

    result = engine.create_subtitles(
        narration_text=test_text,
        duration=12,
        base_name="viral_test"
    )

    print(result)
