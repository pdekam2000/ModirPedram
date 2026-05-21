from pathlib import Path
import time
import os


DOWNLOADS_DIR = Path("downloads")


def get_latest_downloaded_file():
    print("[DownloadHelper] Checking downloads folder...")

    if not DOWNLOADS_DIR.exists():
        print("[DownloadHelper] downloads folder missing.")
        return None

    files = [
        f for f in DOWNLOADS_DIR.iterdir()
        if f.is_file()
    ]

    if not files:
        print("[DownloadHelper] No files found.")
        return None

    latest_file = max(
        files,
        key=os.path.getctime
    )

    print(f"[DownloadHelper] Latest file:")
    print(latest_file)

    return latest_file


def ensure_mp4_extension(file_path):
    file_path = Path(file_path)

    if file_path.suffix.lower() == ".mp4":
        print("[DownloadHelper] Already mp4.")
        return file_path

    new_path = file_path.with_suffix(".mp4")

    print(
        f"[DownloadHelper] Renaming:\n"
        f"{file_path}\n->\n{new_path}"
    )

    file_path.rename(new_path)

    return new_path


def wait_for_new_download(
    timeout=120
):
    print(
        "[DownloadHelper] Waiting for download..."
    )

    start_time = time.time()

    existing = set(
        DOWNLOADS_DIR.glob("*")
    )

    while time.time() - start_time < timeout:

        current = set(
            DOWNLOADS_DIR.glob("*")
        )

        new_files = current - existing

        if new_files:
            newest = max(
                new_files,
                key=os.path.getctime
            )

            print(
                "[DownloadHelper] New download detected:"
            )

            print(newest)

            return newest

        time.sleep(1)

    print(
        "[DownloadHelper] Download timeout."
    )

    return None