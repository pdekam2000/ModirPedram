from pathlib import Path
from utils.ffmpeg_stitcher import FFmpegStitcher


DOWNLOADS_DIR = Path("downloads")
OUTPUT_DIR = Path("outputs/final_videos")
OUTPUT_PATH = OUTPUT_DIR / "final_video.mp4"


def find_latest_mp4_clips(limit=3):
    clips = sorted(
        DOWNLOADS_DIR.glob("*.mp4"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if len(clips) < limit:
        raise RuntimeError(
            f"Need at least {limit} mp4 clips in downloads folder, found {len(clips)}."
        )

    selected = list(reversed(clips[:limit]))

    print("[Test] Selected clips:")
    for clip in selected:
        print(" -", clip)

    return selected


def main():
    clips = find_latest_mp4_clips(limit=3)

    stitcher = FFmpegStitcher(
    ffmpeg_path=r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
   )
    final_video = stitcher.stitch_clips(
        clip_paths=clips,
        output_path=str(OUTPUT_PATH),
    )

    print("\nDONE")
    print("Final video:", final_video)


if __name__ == "__main__":
    main()