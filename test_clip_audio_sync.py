from pathlib import Path

from utils.ffmpeg_clip_audio_merger import FFmpegClipAudioMerger


FFMPEG_PATH = r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"


def find_latest_clips(limit=3):
    clips = sorted(
        Path("downloads").glob("*.mp4"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if len(clips) < limit:
        raise RuntimeError(f"Need {limit} mp4 clips, found {len(clips)}.")

    return list(reversed(clips[:limit]))


def main():
    merger = FFmpegClipAudioMerger(ffmpeg_path=FFMPEG_PATH)

    clips = find_latest_clips(limit=3)

    voices = [
        Path("outputs/audio/timeline/clip_1_voice.mp3"),
        Path("outputs/audio/timeline/clip_2_voice.mp3"),
        Path("outputs/audio/timeline/clip_3_voice.mp3"),
    ]

    output_dir = Path("outputs/synced_clips")
    output_dir.mkdir(parents=True, exist_ok=True)

    synced_files = []

    for index, (clip, voice) in enumerate(zip(clips, voices), start=1):
        output_path = output_dir / f"synced_clip_{index}.mp4"

        synced_file = merger.merge_clip_audio(
            video_path=str(clip),
            audio_path=str(voice),
            output_path=str(output_path),
        )

        synced_files.append(synced_file)

    print("\nDONE")
    print("Synced clips:")
    for file in synced_files:
        print(" -", file)


if __name__ == "__main__":
    main()