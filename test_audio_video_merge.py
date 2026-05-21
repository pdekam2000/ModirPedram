from utils.ffmpeg_audio_merger import FFmpegAudioMerger


def main():
    merger = FFmpegAudioMerger(
        ffmpeg_path=r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
    )

    final_video = merger.merge_audio(
        video_path="outputs/final_videos/final_video.mp4",
        audio_path="outputs/audio/selfcare_narration.mp3",
        output_path="outputs/final_videos/final_with_audio.mp4",
    )

    print("\nDONE")
    print("Final video:", final_video)


if __name__ == "__main__":
    main()