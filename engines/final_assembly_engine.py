from utils.final_cinematic_assembler import (
    FinalCinematicAssembler
)


class FinalAssemblyEngine:

    def __init__(
        self,
        ffmpeg_path,
    ):

        self.assembler = (
            FinalCinematicAssembler(
                ffmpeg_path=ffmpeg_path
            )
        )

    def assemble_video(
        self,
        synced_files,
        episode_folder,
    ):

        print("\n[4] Final cinematic assembly...")

        assembled_video = (
            self.assembler.assemble(
                clip_paths=synced_files,
                output_path=(
                    f"outputs/full_test/"
                    f"{episode_folder}/"
                    f"assembled_video.mp4"
                ),
            )
        )

        return assembled_video