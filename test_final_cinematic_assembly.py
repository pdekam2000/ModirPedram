from pathlib import Path

from utils.final_cinematic_assembler import FinalCinematicAssembler


FFMPEG_PATH = r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"


def main():
    assembler = FinalCinematicAssembler(
        ffmpeg_path=FFMPEG_PATH
    )

    synced_clips = [
        Path("outputs/synced_clips/synced_clip_1.mp4"),
        Path("outputs/synced_clips/synced_clip_2.mp4"),
        Path("outputs/synced_clips/synced_clip_3.mp4"),
    ]

    final_video = assembler.assemble(
        clip_paths=[str(c) for c in synced_clips],
        output_path="outputs/final_videos/final_selfcare_video.mp4",
    )

    print("\nDONE")
    print("Final cinematic video:")
    print(final_video)


if __name__ == "__main__":
    main()