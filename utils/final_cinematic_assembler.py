from pathlib import Path
import subprocess


class FinalCinematicAssembler:
    def __init__(self, ffmpeg_path: str):
        self.ffmpeg_path = ffmpeg_path

    def assemble(
        self,
        clip_paths,
        output_path: str,
    ):
        output = Path(output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)

        concat_file = output.parent / "final_concat_list.txt"

        with open(concat_file, "w", encoding="utf-8") as f:
            for clip in clip_paths:
                clip_path = Path(clip).resolve()
                safe_path = str(clip_path).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(output),
        ]

        print("\n[FinalAssembler] Creating final cinematic video...")

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        print("[FinalAssembler] Final video saved:")
        print(output)

        return str(output)