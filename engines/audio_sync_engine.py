from pathlib import Path

from utils.ffmpeg_clip_audio_merger import (
    FFmpegClipAudioMerger
)


class AudioSyncEngine:

    def __init__(
        self,
        ffmpeg_path,
    ):

        self.merger = FFmpegClipAudioMerger(
            ffmpeg_path=ffmpeg_path
        )

    def sync_clip_audio(
        self,
        downloaded_clips,
        voice_files,
        episode_folder,
    ):

        print("\n[3] Syncing clip audio...")

        synced_dir = (
            Path("outputs/full_test")
            / episode_folder
            / "synced"
        )

        synced_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        synced_files = []

        for index, (clip, voice) in enumerate(
            zip(downloaded_clips, voice_files),
            start=1
        ):

            synced_file = self.merger.merge_clip_audio(
                video_path=str(clip),
                audio_path=str(voice),
                output_path=str(
                    synced_dir / f"synced_clip_{index}.mp4"
                ),
            )

            synced_files.append(synced_file)

        return synced_files